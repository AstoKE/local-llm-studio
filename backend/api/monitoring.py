import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query, Request
from sqlalchemy import select
from backend.core.config import settings
from backend.database.session import SessionLocal
from backend.models.entities import InferenceRun, SystemSample
from backend.services.chat import active_jobs
from backend.services.monitoring import run_dict
from backend.services.system import system_snapshot

router = APIRouter(prefix='/api')


def read_history(minutes: int, model: str | None, before_id: int | None) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    with SessionLocal() as session:
        samples = session.scalars(select(SystemSample).where(SystemSample.created_at >= cutoff).order_by(SystemSample.id).limit(20000)).all()
        # Select evenly spaced actual observations, never interpolate missing readings.
        if len(samples) > 600:
            samples = [samples[round(i * (len(samples)-1) / 599)] for i in range(600)]
        query = select(InferenceRun).where(InferenceRun.created_at >= cutoff)
        if model:
            query = query.where(InferenceRun.model == model)
        if before_id:
            query = query.where(InferenceRun.id < before_id)
        runs = session.scalars(query.order_by(InferenceRun.id.desc()).limit(101)).all()
        models = list(session.scalars(select(InferenceRun.model).distinct().order_by(InferenceRun.model)))
        return dict(system_history=[dict(id=s.id, **s.payload) for s in samples],
                    runs=[run_dict(r) for r in runs[:100]], has_more=len(runs) > 100, models=models)


@router.get('/monitoring')
async def monitoring(request: Request, minutes: int = Query(60, ge=1, le=10080),
                     model: str | None = Query(None, max_length=200), before_id: int | None = Query(None, gt=0)):
    history = await asyncio.to_thread(read_history, minutes, model, before_id)
    sampler = getattr(request.app.state, 'metrics', None)
    current = sampler.latest if sampler and sampler.latest else await system_snapshot()
    sampled_at = datetime.fromisoformat(current['sampled_at'])
    stale = (datetime.now(timezone.utc) - sampled_at).total_seconds() > settings().metrics_interval_seconds * 3
    return {**history, 'current': current, 'active_jobs': len(active_jobs), 'stale': stale,
            'sampler_error': sampler.error if sampler else 'Background sampler is not running.',
            'interval_seconds': settings().metrics_interval_seconds,
            'retention_hours': settings().metrics_retention_hours}
