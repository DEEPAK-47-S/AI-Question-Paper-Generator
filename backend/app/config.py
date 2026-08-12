"""Application configuration loaded exclusively from environment variables."""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NIET AI Question Paper Generator"
    app_env: str = "development"
    database_url: str = "sqlite:///./niet_qpg.db"
    secret_key: str = "development-only-change-this-secret"
    access_token_expire_minutes: int = 480

    ai_provider: str = "local"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"

    max_upload_size: int = 25 * 1024 * 1024
    upload_dir: Path = Path("uploads")
    generated_dir: Path = Path("generated_papers")
    vector_db_url: str = "local://lexical"
    allowed_origins: List[str] = ["http://localhost:8000"]
    ocr_language: str = "eng"
    url_fetch_max_bytes: int = 25 * 1024 * 1024

    bootstrap_admin_email: str = "admin@niet.edu"
    bootstrap_admin_password: str = "ChangeMe123!"
    bootstrap_teacher_email: str = "teacher@niet.edu"
    bootstrap_teacher_password: str = "Teacher123!"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.secret_key == "development-only-change-this-secret":
        raise RuntimeError("SECRET_KEY must be configured in production")
    if settings.is_production and settings.bootstrap_admin_password == "ChangeMe123!":
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be changed in production")
    settings.ensure_directories()
    return settings
