from sqlalchemy import select
from backend.database.session import SessionLocal
from backend.models.entities import Record
from backend.schemas.inference import Configuration
from backend.core.config import settings

def application_settings() -> dict:
    defaults={'ollama_url':str(settings().ollama_url),'default_model':'','configuration':Configuration().model_dump(),'theme':'dark'}
    with SessionLocal() as session:
        record=session.scalar(select(Record).where(Record.kind=='app_settings'))
        return {**defaults,**(record.payload if record else {})}

def save_settings(payload: dict) -> None:
    with SessionLocal.begin() as session:
        record=session.scalar(select(Record).where(Record.kind=='app_settings'))
        if record:
            record.payload={**record.payload,**payload}
        else:
            session.add(Record(kind='app_settings',name='application',payload=payload))
