import hmac
from fastapi import HTTPException, Request
from backend.core.config import settings

async def administrator(request: Request) -> None:
    token = settings().admin_token
    if len(token) < 32:
        raise HTTPException(403, 'Set STUDIO_ADMIN_TOKEN to a random secret of at least 32 characters and restart the backend.')
    supplied = request.headers.get('authorization', '')
    if not hmac.compare_digest(supplied, f'Bearer {token}'):
        raise HTTPException(401, 'Administrator token required.')

def allowed_origin(origin: str, configured: str) -> bool:
    """Allow only the configured origin, with loopback hostname aliases on its port."""
    from urllib.parse import urlsplit
    try:
        actual, expected = urlsplit(origin), urlsplit(configured)
        if actual.username or actual.password or actual.query or actual.fragment or actual.path not in {'', '/'}:
            return False
        if actual.scheme not in {'http', 'https'} or actual.scheme != expected.scheme:
            return False
        default_port = 443 if actual.scheme == 'https' else 80
        if (actual.port or default_port) != (expected.port or default_port):
            return False
        loopback = {'localhost', '127.0.0.1', '::1'}
        return actual.hostname == expected.hostname or (actual.hostname in loopback and expected.hostname in loopback)
    except ValueError:
        return False

async def same_origin(request: Request) -> None:
    origin = request.headers.get('origin')
    if origin and not allowed_origin(origin, str(settings().web_origin)):
        raise HTTPException(403, 'Origin is not allowed. Set STUDIO_WEB_ORIGIN to the frontend origin and restart the backend.')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Cross-site mutation denied.')
