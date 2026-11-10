import hmac
from fastapi import HTTPException, Request
from backend.core.config import settings

def is_admin(request: Request) -> bool:
    from backend.services.auth import COOKIE, session_valid
    token = settings().admin_token
    supplied = request.headers.get('authorization', '')
    bearer = len(token) >= 32 and hmac.compare_digest(supplied.encode(), f'Bearer {token}'.encode())
    return bearer or session_valid(request.cookies.get(COOKIE))

async def administrator(request: Request) -> None:
    if not is_admin(request):
        if len(settings().admin_token) < 32 and not settings().admin_password_hash:
            raise HTTPException(403, 'Configure an administrator password hash or STUDIO_ADMIN_TOKEN first.')
        raise HTTPException(401, 'Administrator authentication required.')

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

def allowed_host(host: str) -> bool:
    from urllib.parse import urlsplit
    try:
        parsed=urlsplit('//'+host)
        return bool(not parsed.username and not parsed.password and not parsed.path and not parsed.query and not parsed.fragment
                    and parsed.hostname in {'127.0.0.1','localhost','::1',settings().web_origin.host})
    except ValueError:
        return False
