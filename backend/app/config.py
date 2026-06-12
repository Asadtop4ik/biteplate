"""Application settings loaded from environment (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    APP_ENV: str = 'dev'
    SECRET_KEY: str = 'change-me'
    DATABASE_URL: str = 'postgresql+psycopg://biteplate:biteplate@postgres:5432/biteplate'
    REDIS_URL: str = 'redis://redis:6379/0'
    BROKER_URL: str = 'redis://redis:6379/1'
    RESULT_BACKEND: str = 'redis://redis:6379/2'
    SESSION_COOKIE: str = 'biteplate_session'
    TAX_RATE: float = 0.12
    DEFAULT_COMBO_DISCOUNT: float = 0.10


settings = Settings()
