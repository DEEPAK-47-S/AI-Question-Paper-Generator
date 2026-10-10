from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Government Resource Planning Platform"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "sqlite+aiosqlite:///./gov_resource_planner.db"
    SECRET_KEY: str = "super-secret-key-for-development"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    class Config:
        case_sensitive = True

settings = Settings()
