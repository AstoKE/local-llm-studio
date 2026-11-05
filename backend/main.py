from contextlib import asynccontextmanager
import hmac
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from backend.core.config import settings
from backend.api.routes import router
from backend.api.workspace import router as workspace_router
from backend.providers.ollama import OllamaProvider
from backend.providers.base import ProviderUnavailable

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(base_url=str(settings().ollama_url), timeout=4, trust_env=False) as client:
        app.state.provider = OllamaProvider(client)
        yield

app = FastAPI(title='Local LLM Studio', version='0.1.0', lifespan=lifespan)

@app.middleware('http')
async def access_control(request: Request, call_next):
    # Backend is loopback-only. LAN mode must use an authenticated reverse proxy.
    if request.client and request.client.host not in {'127.0.0.1', '::1', 'testclient'}:
        token = settings().admin_token
        supplied = request.headers.get('authorization', '')
        if len(token) < 32 or not hmac.compare_digest(supplied, f'Bearer {token}'):
            return JSONResponse({'detail': 'Remote access requires administrator authentication.'}, status_code=401)
    return await call_next(request)

@app.exception_handler(ProviderUnavailable)
async def unavailable(request: Request, exc: ProviderUnavailable):
    return JSONResponse({'detail': str(exc)}, status_code=503)

app.include_router(router)

app.include_router(workspace_router)
