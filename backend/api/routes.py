import asyncio
from fastapi import APIRouter, Request
from sqlalchemy import text, select
from backend.database.session import SessionLocal
from backend.models.entities import Conversation, Record
from backend.providers.base import ProviderUnavailable
from backend.services.system import system_snapshot
from backend.services.chat import active_jobs

router = APIRouter(prefix='/api')

@router.get('/health')
async def health():
    with SessionLocal() as session:
        session.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'connected', 'phase': 2}

@router.get('/models')
async def models(request: Request):
    return {'models': await request.app.state.provider.models()}

@router.get('/dashboard')
async def dashboard(request: Request):
    provider = request.app.state.provider
    async def runtime():
        try:
            version, models, loaded = await asyncio.gather(provider.status(), provider.models(), provider.loaded())
            return dict(connected=True, version=version.get('version'), models=models, loaded=loaded, error=None)
        except ProviderUnavailable as exc:
            return dict(connected=False, version=None, models=None, loaded=None, error=str(exc))
    ollama, system = await asyncio.gather(runtime(), system_snapshot())
    with SessionLocal() as session:
        conversations = session.scalars(select(Conversation).order_by(Conversation.created_at.desc()).limit(5)).all()
        benchmarks = session.scalars(select(Record).where(Record.kind == 'benchmark').order_by(Record.created_at.desc()).limit(5)).all()
    return dict(ollama=ollama, system=system, conversations=[dict(id=c.id, title=c.title) for c in conversations],
                benchmarks=[dict(id=b.id, name=b.name, payload=b.payload) for b in benchmarks], active_jobs=len(active_jobs))
