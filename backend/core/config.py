from functools import lru_cache
from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_prefix='STUDIO_')
    ollama_url: HttpUrl = 'http://127.0.0.1:11434'
    database_url: str = 'sqlite:///./data/studio.db'
    admin_token: str = ''

@lru_cache
def settings() -> Settings:
    return Settings()
