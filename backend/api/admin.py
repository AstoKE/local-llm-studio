import asyncio
from pathlib import Path
import platform
from typing import Literal
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, HttpUrl, field_validator
from sqlalchemy import delete, inspect, select, text
from backend.core.config import settings
from backend.core.security import administrator, same_origin
from backend.database.session import SessionLocal, engine
from backend.models.entities import InferenceRun, Record, SystemSample
from backend.providers.ollama import OllamaProvider
from backend.schemas.inference import Configuration, StrictModel
from backend.services import runtime
from backend.services.chat import active_jobs
from backend.services.preferences import application_settings, save_settings

router=APIRouter(prefix='/api',dependencies=[Depends(same_origin)])

class AdminSettings(StrictModel):
    ollama_url: HttpUrl
    default_model: str = Field('',max_length=200,pattern=r'^[a-zA-Z0-9._:/-]*$')
    configuration: Configuration
    @field_validator('ollama_url')
    @classmethod
    def no_credentials(cls,value:HttpUrl):
        if value.username or value.password or value.query or value.fragment:
            raise ValueError('Provider URL must not contain credentials, query or fragment.')
        return value

class Maintenance(StrictModel):
    operation: Literal['vacuum','clear_metrics']

class Theme(StrictModel):
    theme: Literal['dark','light','system']

def ensure_idle():
    if active_jobs or runtime.benchmark_active or runtime.model_operations:
        raise HTTPException(409,'Wait until inference, benchmarks and model operations finish.')

@router.get('/preferences')
async def preferences():
    values=application_settings()
    return {key:values[key] for key in ['default_model','configuration','theme']}

@router.put('/preferences')
async def theme(body:Theme):
    save_settings({'theme':body.theme})
    return {'saved':True}

@router.get('/admin/settings',dependencies=[Depends(administrator)])
async def get_settings():
    return {**application_settings(),'provider':'ollama','lan_mode':settings().lan_mode,'web_origin':str(settings().web_origin),
            'metrics_interval_seconds':settings().metrics_interval_seconds,'metrics_retention_hours':settings().metrics_retention_hours}

@router.put('/admin/settings',dependencies=[Depends(administrator)])
async def put_settings(body:AdminSettings,request:Request):
    ensure_idle()
    values=body.model_dump(mode='json')
    save_settings(values)
    request.app.state.provider.client.base_url=httpx.URL(str(body.ollama_url))
    return {'saved':True}

@router.post('/admin/connection-test',dependencies=[Depends(administrator)])
async def connection_test(body:AdminSettings):
    async with httpx.AsyncClient(base_url=str(body.ollama_url),timeout=5,trust_env=False) as client:
        return await OllamaProvider(client).status()

@router.get('/admin/health',dependencies=[Depends(administrator)])
async def health():
    with engine.connect() as connection:
        check=connection.execute(text('PRAGMA quick_check')).scalar()
        revision=connection.execute(text('SELECT version_num FROM alembic_version')).scalar() if inspect(engine).has_table('alembic_version') else None
        samples=connection.execute(text('SELECT COUNT(*) FROM system_samples')).scalar()
        runs=connection.execute(text('SELECT COUNT(*) FROM inference_runs')).scalar()
    path=Path(engine.url.database or '')
    return dict(database=check,revision=revision,database_bytes=path.stat().st_size if path.is_file() else None,
                system_samples=samples,inference_runs=runs,python=platform.python_version(),os=platform.system(),
                active_jobs=len(active_jobs),benchmark_active=runtime.benchmark_active)

@router.post('/admin/maintenance',dependencies=[Depends(administrator)])
async def maintenance(body:Maintenance,request:Request):
    ensure_idle()
    def perform():
        if body.operation=='clear_metrics':
            with SessionLocal.begin() as session:
                session.execute(delete(SystemSample))
                session.execute(delete(InferenceRun))
        else:
            with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
                connection.execute(text('VACUUM'))
    # Block admission while SQLite maintenance runs, without exposing SQL or paths.
    runtime.model_operations.add('database-maintenance')
    try:
        sampler=getattr(request.app.state,'metrics',None)
        lock=getattr(sampler,'storage_lock',asyncio.Lock())
        async with lock:
            await asyncio.to_thread(perform)
    finally:
        runtime.model_operations.discard('database-maintenance')
    return {'completed':True}
