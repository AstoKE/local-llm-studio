import hashlib
import hmac
import secrets
import time
from sqlalchemy import delete, select
from backend.database.session import SessionLocal
from backend.models.entities import Record
from backend.core.config import settings

COOKIE = 'studio_session'

def hash_password(password: str) -> str:
    if len(password)<12:
        raise ValueError('Use at least 12 characters.')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,maxmem=64*1024**2)
    return f'scrypt${salt.hex()}${digest.hex()}'

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split('$')
        if algorithm!='scrypt' or len(salt)!=32 or len(expected)!=128:
            return False
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,maxmem=64*1024**2)
        return hmac.compare_digest(actual,bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False

def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def session_valid(token: str | None) -> bool:
    if not token or len(token)>128:
        return False
    with SessionLocal() as session:
        record=session.scalar(select(Record).where(Record.kind=='auth_session',Record.name==digest_token(token)))
        return bool(record and record.payload.get('expires_at',0)>time.time() and record.payload.get('credential_version')==digest_token(settings().admin_password_hash))

def new_session() -> str:
    token=secrets.token_urlsafe(32)
    with SessionLocal.begin() as session:
        rows=session.scalars(select(Record).where(Record.kind=='auth_session').order_by(Record.id.desc())).all()
        for index,row in enumerate(rows):
            if row.payload.get('expires_at',0)<=time.time() or index>=99:
                session.delete(row)
        session.add(Record(kind='auth_session',name=digest_token(token),payload={'expires_at':time.time()+settings().session_hours*3600,'role':'admin','credential_version':digest_token(settings().admin_password_hash)}))
    return token

def revoke(token: str | None) -> None:
    if token:
        with SessionLocal.begin() as session:
            session.execute(delete(Record).where(Record.kind=='auth_session',Record.name==digest_token(token)))
