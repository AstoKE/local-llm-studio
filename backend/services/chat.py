from contextlib import aclosing
import json
import time
from fastapi import HTTPException
from sqlalchemy import delete, select
from backend.database.session import SessionLocal
from backend.models.entities import Conversation, Message
from backend.providers.base import InferenceProvider, ProviderUnavailable
from backend.schemas.inference import ChatInput

# One process / one worker: serialize each conversation; unrelated chats may run concurrently.
active_conversations: set[int] = set()
active_jobs: set[str] = set()

def event(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False) + '\n'

def prepare_chat(body: ChatInput) -> list[dict]:
    if body.conversation_id is None:
        if body.regenerate or body.edit_message_id:
            raise HTTPException(422, 'Edit/regenerate requires a saved conversation.')
        if not body.content.strip():
            raise HTTPException(422, 'Message cannot be empty.')
        return [m.model_dump() for m in body.history] + [{'role': 'user', 'content': body.content}]
    if body.history:
        raise HTTPException(422, 'Saved conversations use server history.')
    with SessionLocal.begin() as session:
        conversation = session.get(Conversation, body.conversation_id)
        if not conversation:
            raise HTTPException(404, 'Conversation not found.')
        messages = session.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id)).all()
        if body.edit_message_id:
            target = next((m for m in messages if m.id == body.edit_message_id and m.role == 'user'), None)
            if not target or not body.content.strip():
                raise HTTPException(422, 'A nonempty user message is required for editing.')
            session.execute(delete(Message).where(Message.conversation_id == conversation.id, Message.id >= target.id))
            messages = [m for m in messages if m.id < target.id]
        elif body.regenerate:
            if not messages:
                raise HTTPException(422, 'No message to regenerate.')
            if messages[-1].role == 'assistant':
                session.delete(messages.pop())
            if not messages or messages[-1].role != 'user':
                raise HTTPException(422, 'No user message to regenerate.')
        if not body.regenerate:
            if not body.content.strip():
                raise HTTPException(422, 'Message cannot be empty.')
            session.add(Message(conversation_id=conversation.id, role='user', content=body.content))
        conversation.model = body.model
        conversation.configuration = body.configuration.model_dump()
        history = [dict(role=m.role, content=m.content) for m in messages if m.statistics.get('status', 'completed') == 'completed' or m.role == 'user']
        if not body.regenerate:
            history.append(dict(role='user', content=body.content))
        return history

async def generate(provider: InferenceProvider, body: ChatInput, history: list[dict], job: str):
    started = time.perf_counter()
    content = ''
    stats: dict = {'status': 'interrupted'}
    completed = False
    payload = dict(model=body.model, messages=([{'role': 'system', 'content': body.configuration.system_prompt}] if body.configuration.system_prompt else []) + history,
                   options=body.configuration.options.model_dump(), keep_alive=body.configuration.keep_alive)
    try:
        async with aclosing(provider.chat(payload)) as upstream:
            async for chunk in upstream:
                text = chunk.get('message', {}).get('content', '')
                if text:
                    if 'server_ttft_seconds' not in stats:
                        stats['server_ttft_seconds'] = time.perf_counter() - started
                    content += text
                    yield event({'type': 'token', 'content': text})
                if chunk.get('done'):
                    stats.update({k: chunk[k] for k in ['eval_count', 'eval_duration', 'prompt_eval_count', 'prompt_eval_duration', 'total_duration', 'load_duration', 'done_reason'] if k in chunk})
                    stats['status'] = 'completed'
                    completed = True
                    break
        if not completed:
            raise ProviderUnavailable('Ollama stream ended before completion.')
        yield event({'type': 'done', 'statistics': stats})
    except ProviderUnavailable as exc:
        stats['status'] = 'failed'
        yield event({'type': 'error', 'detail': str(exc)})
    finally:
        # Persist partial output on disconnect, without sending it in subsequent context.
        if body.conversation_id is not None:
            if content or completed:
                with SessionLocal.begin() as session:
                    session.add(Message(conversation_id=body.conversation_id, role='assistant', content=content, statistics=stats))
            active_conversations.discard(body.conversation_id)
        active_jobs.discard(job)
