from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "公文辅助系统"
    APP_VERSION: str = "1.0.0"
    SECRET_KEY: str = "claw-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://claw:claw_dev_2026@localhost:5432/claw"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # File storage
    UPLOAD_DIR: str = "/data/uploads"
    LOG_DIR: str = "/data/logs"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Encryption key for API keys (32 bytes hex)
    ENCRYPTION_KEY: str = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"

    class Config:
        env_file = ".env"


settings = Settings()

# Ensure upload directory exists
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
