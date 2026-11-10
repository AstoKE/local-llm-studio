import asyncio
from contextlib import aclosing, suppress
from datetime import datetime, timezone
import logging
import time
import uuid
import psutil
from sqlalchemy import select
from backend.database.session import SessionLocal
from backend.models.entities import Record
from backend.providers.base import InferenceProvider, ProviderUnavailable
from backend.schemas.benchmark import BenchmarkInput
from backend.services import runtime
from backend.services.chat import active_jobs
from backend.services.monitoring import save_run

logger = logging.getLogger(__name__)

def utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def update_record(identifier: int, payload: dict) -> None:
    with SessionLocal.begin() as session:
        record = session.get(Record, identifier)
        if record:
            record.payload = dict(payload)

async def measure(provider: InferenceProvider, model: str, prompt: str, configuration: dict, metrics) -> dict:
    memory_peak = psutil.virtual_memory().used
    gpu_peak: dict[str, float] = {}
    wall_started = time.time()
    async def sample_memory():
        nonlocal memory_peak
        while True:
            memory_peak = max(memory_peak, psutil.virtual_memory().used)
            snapshot = metrics.latest if metrics else None
            observed = datetime.fromisoformat(snapshot['sampled_at']).timestamp() if snapshot and snapshot.get('sampled_at') else 0
            for gpu in ((snapshot or {}).get('gpu') or []) if observed >= wall_started else []:
                used = gpu.get('memory_used_mib')
                if used is not None:
                    gpu_peak[gpu['id']] = max(gpu_peak.get(gpu['id'], 0), used)
            await asyncio.sleep(.25)
    tracker = asyncio.create_task(sample_memory())
    started = time.perf_counter()
    stats: dict = {}
    completed = False
    try:
        messages = ([{'role':'system','content':configuration['system_prompt']}] if configuration['system_prompt'] else []) + [{'role':'user','content':prompt}]
        async with aclosing(provider.chat(dict(model=model, messages=messages, options=configuration['options'], keep_alive=configuration['keep_alive']))) as upstream:
            async for chunk in upstream:
                if chunk.get('message', {}).get('content') and 'server_ttft_seconds' not in stats:
                    stats['server_ttft_seconds'] = time.perf_counter() - started
                if chunk.get('done'):
                    stats.update({k:chunk[k] for k in ['eval_count','eval_duration','prompt_eval_count','prompt_eval_cached_count','prompt_eval_duration','total_duration','load_duration'] if k in chunk})
                    completed = True
                    break
        if not completed:
            raise ProviderUnavailable('Provider stream ended without completion.')
        stats['status'] = 'completed'
    except ProviderUnavailable as exc:
        stats.update(status='failed', error=str(exc))
    finally:
        stats['server_duration_seconds'] = time.perf_counter() - started
        memory_peak = max(memory_peak, psutil.virtual_memory().used)
        tracker.cancel()
        with suppress(asyncio.CancelledError):
            await tracker
    return dict(statistics=stats, host_memory_peak_bytes=memory_peak, gpu_memory_peak_mib=gpu_peak,
                memory_note='Whole-host RAM sampled every 250ms; GPU includes only host samples timestamped during this run, may miss short peaks. Not model allocation.')

class BenchmarkManager:
    def __init__(self, provider: InferenceProvider, metrics=None):
        self.provider = provider
        self.metrics = metrics
        self.task: asyncio.Task | None = None
        self.identifier: int | None = None

    def start(self, body: BenchmarkInput) -> int:
        from fastapi import HTTPException
        if runtime.benchmark_active or active_jobs or runtime.model_operations:
            raise HTTPException(409, 'Wait for active inference or model operations before benchmarking.')
        payload = dict(status='running', started_at=utc(), definition=body.model_dump(), results=[], progress=0,
                       total=len(body.configurations)*(body.warmups+body.repeats))
        with SessionLocal.begin() as session:
            record = Record(kind='benchmark', name=body.name, payload=payload)
            session.add(record)
            session.flush()
            identifier = record.id
        runtime.benchmark_active = True
        self.identifier = identifier
        self.task = asyncio.create_task(self.run(identifier, body, payload))
        return identifier

    async def run(self, identifier: int, body: BenchmarkInput, payload: dict) -> None:
        try:
            for index, variant in enumerate(body.configurations):
                for repetition in range(body.warmups + body.repeats):
                    job = uuid.uuid4().hex
                    active_jobs.add(job)
                    try:
                        result = await measure(self.provider, body.model, body.prompt, variant.configuration.model_dump(), self.metrics)
                    finally:
                        active_jobs.discard(job)
                    warmup = repetition < body.warmups
                    result.update(configuration_index=index, configuration_name=variant.name, warmup=warmup,
                                  repetition=repetition-body.warmups+1 if not warmup else repetition+1)
                    payload['results'].append(result)
                    payload['progress'] += 1
                    if not warmup:
                        save_run(job, body.model, 'benchmark', result['statistics'])
                    update_record(identifier, payload)
                    if result['statistics']['status'] != 'completed':
                        payload['status'] = 'failed'
                        payload['error'] = result['statistics'].get('error', 'Provider did not complete the run.')
                        return
            payload['status'] = 'completed'
        except asyncio.CancelledError:
            payload['status'] = 'cancelled'
            raise
        except Exception:
            payload.update(status='failed', error='Benchmark failed. Check backend logs and runtime availability.')
            logger.exception('Benchmark failed')
        finally:
            payload['finished_at'] = utc()
            try:
                update_record(identifier, payload)
            finally:
                runtime.benchmark_active = False
                self.identifier = None

    async def cancel(self, identifier: int) -> None:
        from fastapi import HTTPException
        if self.identifier != identifier or not self.task:
            raise HTTPException(409, 'This benchmark is not active in this process.')
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task
        # A task cancelled before its first turn never enters run()'s finally block.
        if self.identifier == identifier:
            try:
                with SessionLocal() as session:
                    record = session.get(Record, identifier)
                    payload = dict(record.payload) if record else {}
                payload.update(status='cancelled', finished_at=utc())
                update_record(identifier, payload)
            finally:
                runtime.benchmark_active = False
                self.identifier = None

    async def shutdown(self):
        if self.identifier is not None:
            await self.cancel(self.identifier)

    @staticmethod
    def recover():
        with SessionLocal.begin() as session:
            for record in session.scalars(select(Record).where(Record.kind == 'benchmark')):
                if record.payload.get('status') == 'running':
                    record.payload = {**record.payload, 'status':'interrupted', 'finished_at':utc()}
