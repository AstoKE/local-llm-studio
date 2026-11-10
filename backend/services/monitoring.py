import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from backend.core.config import settings
from backend.database.session import SessionLocal
from backend.models.entities import InferenceRun, SystemSample
from backend.services.system import system_snapshot

logger = logging.getLogger(__name__)


def trim_history(session) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings().metrics_retention_hours)
    session.execute(delete(SystemSample).where(SystemSample.created_at < cutoff))
    # Also cap rows if interval or clock changes; inference rows never retain prompts.
    for entity, maximum in [(SystemSample, 20000), (InferenceRun, 10000)]:
        retained = select(entity.id).order_by(entity.id.desc()).limit(maximum)
        session.execute(delete(entity).where(entity.id.not_in(retained)))


def save_sample(snapshot: dict) -> None:
    with SessionLocal.begin() as session:
        session.add(SystemSample(payload=snapshot))
        session.flush()
        trim_history(session)


def save_run(job: str, model: str, source: str, statistics: dict) -> None:
    with SessionLocal.begin() as session:
        session.add(InferenceRun(job_id=job, model=model, source=source, statistics=statistics))
        session.flush()
        retained = select(InferenceRun.id).order_by(InferenceRun.id.desc()).limit(10000)
        session.execute(delete(InferenceRun).where(InferenceRun.id.not_in(retained)))


def run_dict(row: InferenceRun) -> dict:
    s = row.statistics
    count, duration = s.get('eval_count'), s.get('eval_duration')
    rate = count / (duration / 1e9) if isinstance(count, (int, float)) and isinstance(duration, (int, float)) and duration > 0 else None
    return dict(id=row.id, created_at=row.created_at.replace(tzinfo=timezone.utc).isoformat(), model=row.model,
                source=row.source, statistics=s, tokens_per_second=rate)


class MetricsSampler:
    def __init__(self) -> None:
        self.storage_lock = asyncio.Lock()
        self.latest: dict | None = None
        self.error: str | None = None

    async def sample(self) -> None:
        from backend.services.chat import active_jobs
        snapshot = await system_snapshot()
        snapshot['active_jobs'] = len(active_jobs)
        self.latest = snapshot
        try:
            async with self.storage_lock:
                await asyncio.to_thread(save_sample, snapshot)
            self.error = None
        except Exception:
            self.error = 'Performance history could not be saved. Check migrations, disk space and backend logs.'
            logger.exception('Failed to persist system metrics')

    async def run(self) -> None:
        while True:
            try:
                await self.sample()
            except Exception:
                self.error = 'System sampling failed. Check backend logs.'
                logger.exception('System metrics sampling failed')
            await asyncio.sleep(settings().metrics_interval_seconds)
