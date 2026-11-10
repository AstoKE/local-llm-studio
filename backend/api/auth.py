import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from backend.core.config import settings
from backend.core.security import is_admin, same_origin
from backend.schemas.inference import StrictModel
from backend.services.auth import COOKIE, new_session, revoke, verify_password

router=APIRouter(prefix='/api/auth',dependencies=[Depends(same_origin)])
failures: dict[str,list[float]] = {}

class Login(StrictModel):
    password: str = Field(min_length=1,max_length=256)

@router.get('/me')
async def me(request: Request):
    authenticated=is_admin(request)
    return {'authenticated':authenticated,'role':'admin' if authenticated else 'local','lan_mode':settings().lan_mode,'password_configured':bool(settings().admin_password_hash)}

@router.post('/login')
async def login(body:Login,request:Request,response:Response):
    key=request.client.host if request.client else 'unknown'
    now=time.monotonic()
    recent=[t for t in failures.get(key,[]) if t>now-60]
    if len(recent)>=5:
        raise HTTPException(429,'Too many login attempts. Wait one minute.')
    if not settings().admin_password_hash:
        raise HTTPException(503,'Set STUDIO_ADMIN_PASSWORD_HASH using scripts/password_hash.py and restart the backend.')
    if not verify_password(body.password,settings().admin_password_hash):
        failures[key]=recent+[now]
        raise HTTPException(401,'Invalid administrator password.')
    failures.pop(key,None)
    revoke(request.cookies.get(COOKIE))
    token=new_session()
    response.set_cookie(COOKIE,token,httponly=True,secure=settings().lan_mode,samesite='strict',max_age=settings().session_hours*3600,path='/')
    response.headers['Cache-Control']='no-store'
    return {'authenticated':True,'role':'admin'}

@router.post('/logout')
async def logout(request:Request,response:Response):
    revoke(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE,path='/',secure=settings().lan_mode,httponly=True,samesite='strict')
    return {'authenticated':False}
