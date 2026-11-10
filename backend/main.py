from contextlib import asynccontextmanager, suppress
import asyncio
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from backend.core.config import settings
from backend.api.routes import router
from backend.api.workspace import router as workspace_router
from backend.api.monitoring import router as monitoring_router
from backend.providers.ollama import OllamaProvider
from backend.providers.base import ProviderUnavailable
from backend.services.monitoring import MetricsSampler
from backend.services.benchmarks import BenchmarkManager
from backend.core.security import is_admin, same_origin, allowed_host
from backend.core.request_limits import RequestLimitMiddleware
from backend.api.auth import router as auth_router
from backend.api.admin import router as admin_router
from backend.services.preferences import application_settings
from backend.api.benchmarks import router as benchmarks_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings().lan_mode and (settings().web_origin.scheme != 'https' or not settings().admin_password_hash.startswith('scrypt$')):
        raise RuntimeError('LAN mode requires an HTTPS STUDIO_WEB_ORIGIN and STUDIO_ADMIN_PASSWORD_HASH.')
    BenchmarkManager.recover()
    async with httpx.AsyncClient(base_url=application_settings()['ollama_url'], timeout=4, trust_env=False) as client:
        app.state.provider = OllamaProvider(client)
        app.state.metrics = MetricsSampler()
        app.state.benchmarks = BenchmarkManager(app.state.provider, app.state.metrics)
        sampler = asyncio.create_task(app.state.metrics.run())
        try:
            yield
        finally:
            try:
                await app.state.benchmarks.shutdown()
            finally:
                sampler.cancel()
                with suppress(asyncio.CancelledError):
                    await sampler

app = FastAPI(title='Local LLM Studio', version='0.5.0', lifespan=lifespan)
app.add_middleware(RequestLimitMiddleware)

@app.middleware('http')
async def access_control(request: Request, call_next):
    if not allowed_host(request.headers.get('host','')):
        return JSONResponse({'detail':'Host is not allowed.'},status_code=400,headers={'Cache-Control':'no-store'})
    public = request.url.path in {'/api/auth/login','/api/auth/me'}
    try:
        if request.method not in {'GET','HEAD','OPTIONS'}:
            await same_origin(request)
        remote = request.client and request.client.host not in {'127.0.0.1','::1','testclient'}
        if not public and (settings().lan_mode or remote) and not is_admin(request):
            return JSONResponse({'detail':'Administrator login required.'},status_code=401)
    except HTTPException as exc:
        return JSONResponse({'detail':exc.detail},status_code=exc.status_code)
    response = await call_next(request)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(ProviderUnavailable)
async def unavailable(request: Request, exc: ProviderUnavailable):
    return JSONResponse({'detail': str(exc)}, status_code=503)

app.include_router(router)

app.include_router(workspace_router)

app.include_router(monitoring_router)

app.include_router(auth_router)
app.include_router(benchmarks_router)

app.include_router(admin_router)
