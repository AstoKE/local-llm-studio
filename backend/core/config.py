from functools import lru_cache
from pydantic import HttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_prefix='STUDIO_')
    ollama_url: HttpUrl = 'http://127.0.0.1:11434'
    database_url: str = 'sqlite:///./data/studio.db'
    web_origin: HttpUrl = 'http://127.0.0.1:3000'
    admin_token: str = ''
    metrics_interval_seconds: int = Field(5, ge=2, le=60)
    metrics_retention_hours: int = Field(24, ge=1, le=168)

@lru_cache
def settings() -> Settings:
    return Settings()
