from typing import List, Set
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    STORAGE_BUCKET_NAME: str = "submissions"

    # Cron / Internal authentication
    INTERNAL_CRON_SECRET: str = "super-secret-cron-token-123"

    # Google Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_LITE: str = "gemini-2.5-flash-lite"
    GEMINI_MODEL_FLASH: str = "gemini-2.5-flash"

    # Server & Execution
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    BATCH_LIMIT: int = 10
    GEMINI_CALL_DELAY_MS: int = 1000
    FRONTEND_URL: str = "http://localhost:3000"

    # File uploads limits
    MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".md", ".txt"}
    ALLOWED_MIME_TYPES: Set[str] = {
        "application/pdf",
        "text/markdown",
        "text/plain",
        "application/octet-stream"
    }

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "https://api.eduagents.app",
        "*"
    ]


settings = Settings()
