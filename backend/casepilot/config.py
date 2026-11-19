from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///data/casepilot.db"
    checkpoint_path: str = "data/checkpoints.db"
    service_database_url: str = "sqlite:///data/service.db"
    service_url: str = "http://127.0.0.1:8001"
    service_token: str = "local-service-only"
    user_token: str = "local-user-only"
    approver_token: str = "local-approver-only"
    viewer_token: str = "local-viewer-only"
    cors_origin: str = "http://localhost:5173"
    tool_timeout: float = 5.0


@lru_cache
def settings() -> Settings:
    return Settings()
