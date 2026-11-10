from contextlib import aclosing
import uuid
from backend.services import runtime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from backend.services.streaming import ManagedStreamingResponse
from sqlalchemy import delete, select
from backend.core.security import administrator, same_origin
from backend.database.session import SessionLocal
from backend.models.entities import Conversation, Message, Record
from backend.providers.base import ProviderUnavailable
from backend.schemas.inference import ChatInput, ConversationInput, ModelInput, PresetInput, ConversationSnapshot, Configuration
from backend.services.chat import active_conversations, active_jobs, event, generate, prepare_chat

router = APIRouter(prefix='/api', dependencies=[Depends(same_origin)])

def conversation_dict(c: Conversation) -> dict:
    return dict(id=c.id, title=c.title, model=c.model, configuration=c.configuration)

@router.get('/conversations')
async def conversations(q: str = ''):
    with SessionLocal() as session:
        rows = session.scalars(select(Conversation).where(Conversation.title.contains(q[:200], autoescape=True)).order_by(Conversation.id.desc()).limit(200)).all()
        return [conversation_dict(c) for c in rows]

@router.post('/conversations', status_code=201)
async def create(body: ConversationInput):
    with SessionLocal.begin() as session:
        c = Conversation(title=body.title, model=body.model, configuration=body.configuration.model_dump())
        session.add(c)
        session.flush()
        return conversation_dict(c)

@router.get('/conversations/{conversation_id}')
async def detail(conversation_id: int):
    with SessionLocal() as session:
        c = session.get(Conversation, conversation_id)
        if not c:
            raise HTTPException(404, 'Conversation not found.')
        messages = session.scalars(select(Message).where(Message.conversation_id == c.id).order_by(Message.id)).all()
        return {**conversation_dict(c), 'messages': [dict(id=m.id, role=m.role, content=m.content, statistics=m.statistics) for m in messages]}

@router.put('/conversations/{conversation_id}')
async def update(conversation_id: int, body: ConversationInput):
    if conversation_id in active_conversations:
        raise HTTPException(409, 'Stop generation before changing the conversation.')
    with SessionLocal.begin() as session:
        c = session.get(Conversation, conversation_id)
        if not c:
            raise HTTPException(404, 'Conversation not found.')
        c.title, c.model, c.configuration = body.title, body.model, body.configuration.model_dump()
        return conversation_dict(c)

@router.delete('/conversations/{conversation_id}')
async def remove(conversation_id: int):
    if conversation_id in active_conversations:
        raise HTTPException(409, 'Stop generation before deleting the conversation.')
    with SessionLocal.begin() as session:
        if not session.get(Conversation, conversation_id):
            raise HTTPException(404, 'Conversation not found.')
        session.execute(delete(Message).where(Message.conversation_id == conversation_id))
        session.execute(delete(Conversation).where(Conversation.id == conversation_id))
    return {'deleted': True}

@router.post('/chat')
async def chat(body: ChatInput, request: Request):
    if runtime.benchmark_active or runtime.model_operations:
        raise HTTPException(409, 'Inference is reserved for an active benchmark or model operation.')
    if body.conversation_id in active_conversations:
        raise HTTPException(409, 'This conversation is already generating.')
    history = prepare_chat(body)
    job = uuid.uuid4().hex
    active_jobs.add(job)
    if body.conversation_id is not None:
        active_conversations.add(body.conversation_id)
    def release():
        active_jobs.discard(job)
        if body.conversation_id is not None:
            active_conversations.discard(body.conversation_id)
    return ManagedStreamingResponse(generate(request.app.state.provider, body, history, job), on_close=release, media_type='application/x-ndjson', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

@router.get('/presets')
async def presets():
    with SessionLocal() as session:
        return [dict(id=r.id, name=r.name, configuration=r.payload) for r in session.scalars(select(Record).where(Record.kind == 'preset').order_by(Record.id))]

@router.post('/presets', status_code=201)
async def save_preset(body: PresetInput):
    with SessionLocal.begin() as session:
        r = Record(kind='preset', name=body.name, payload=body.configuration.model_dump())
        session.add(r)
        session.flush()
        return {'id': r.id}

@router.delete('/presets/{preset_id}')
async def delete_preset(preset_id: int):
    with SessionLocal.begin() as session:
        session.execute(delete(Record).where(Record.kind == 'preset', Record.id == preset_id))
    return {'deleted': True}

@router.get('/models/metadata')
async def metadata(request: Request, model: str = Query(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$')):
    validated = ModelInput(model=model)
    return await request.app.state.provider.operation('show', validated.model)

@router.post('/models/{operation}', dependencies=[Depends(administrator)])
async def model_operation(operation: Literal['pull', 'delete', 'load', 'unload'], body: ModelInput, request: Request):
    if runtime.benchmark_active or active_jobs or runtime.model_operations:
        raise HTTPException(409, 'Wait for active inference or model operations to finish.')
    runtime.model_operations.add(body.model)
    if operation != 'pull':
        try:
            return await request.app.state.provider.operation(operation, body.model)
        finally:
            runtime.model_operations.discard(body.model)
    async def download():
        try:
            async with aclosing(request.app.state.provider.pull(body.model)) as upstream:
                async for chunk in upstream:
                    yield event(chunk)
        except ProviderUnavailable as exc:
            yield event({'error': str(exc)})
        finally:
            runtime.model_operations.discard(body.model)
    return ManagedStreamingResponse(download(), on_close=lambda:runtime.model_operations.discard(body.model), media_type='application/x-ndjson', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

@router.post('/conversation-snapshots', status_code=201)
async def save_snapshot(body: 'ConversationSnapshot'):
    with SessionLocal.begin() as session:
        c = Conversation(title=body.title, model=body.model, configuration=body.configuration.model_dump())
        session.add(c)
        session.flush()
        for m in body.messages:
            session.add(Message(conversation_id=c.id, role=m.role, content=m.content, statistics={'status': 'completed', 'source': 'playground_snapshot'}))
        return conversation_dict(c)

@router.get('/model-preferences')
async def model_preferences(model: str = Query(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$')):
    with SessionLocal() as session:
        r = session.scalar(select(Record).where(Record.kind == 'model_preferences', Record.name == model))
        return r.payload if r else None

@router.put('/model-preferences')
async def save_model_preferences(body: Configuration, model: str = Query(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$')):
    ModelInput(model=model)
    with SessionLocal.begin() as session:
        r = session.scalar(select(Record).where(Record.kind == 'model_preferences', Record.name == model))
        if r:
            r.payload = body.model_dump()
        else:
            session.add(Record(kind='model_preferences', name=model, payload=body.model_dump()))
    return {'saved': True}
