# Application settings and environment configuration using Pydantic Settings.
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "XRay Report AI"
    DATABASE_URL: str = "sqlite:///./data/app.db"
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_MB: int = 20
    ENGINE: str = "mock"
    SECRET_KEY: str = "change-this-in-production-to-a-secure-random-secret"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        # Create upload directory
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        # Create database parent folder if using SQLite
        if self.DATABASE_URL.startswith("sqlite:///"):
            db_file_path = self.DATABASE_URL.replace("sqlite:///", "")
            Path(db_file_path).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
