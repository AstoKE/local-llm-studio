from functools import lru_cache
from pydantic import HttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_prefix='STUDIO_')
    ollama_url: HttpUrl = 'http://127.0.0.1:11434'
    database_url: str = 'sqlite:///./data/studio.db'
    web_origin: HttpUrl = 'http://127.0.0.1:3000'
    admin_token: str = ''
    admin_password_hash: str = ''
    lan_mode: bool = False
    max_request_bytes: int = Field(2097152, ge=65536, le=16777216)
    session_hours: int = Field(8, ge=1, le=24)
    metrics_interval_seconds: int = Field(5, ge=2, le=60)
    metrics_retention_hours: int = Field(24, ge=1, le=168)

    @field_validator('ollama_url')
    @classmethod
    def private_credentials(cls,value:HttpUrl):
        if value.username or value.password or value.query or value.fragment:
            raise ValueError('Ollama URL must not contain credentials, query or fragment.')
        return value

    @field_validator('admin_password_hash')
    @classmethod
    def valid_password_hash(cls,value:str):
        import re
        if value and not re.fullmatch(r'scrypt\$[0-9a-f]{32}\$[0-9a-f]{128}',value):
            raise ValueError('Generate STUDIO_ADMIN_PASSWORD_HASH using scripts/password_hash.py.')
        return value

@lru_cache
def settings() -> Settings:
    return Settings()
