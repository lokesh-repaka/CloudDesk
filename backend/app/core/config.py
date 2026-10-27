import json
from functools import lru_cache
from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core runtime & environment
    DEMO_MODE: bool = True
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Authentication & Security
    JWT_SECRET: str = "dev-secret-change-in-prod"
    SUPABASE_JWT_SECRET: str | None = None

    # Persistence
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/support.db"
    CHECKPOINT_DB_PATH: str = "./data/checkpoints.db"

    # Cache & Rate Limiting
    REDIS_URL: str = ""
    USE_FAKE_REDIS: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120

    # LLM & Providers
    LLM_PROVIDER: str = "fake"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "fake-model"

    # Embeddings & Vector Store
    EMBEDDING_PROVIDER: str = "fake"
    EMBEDDING_MODEL: str = "fake-embedding"
    EMBEDDING_DIMENSIONS: int = 384
    VECTOR_STORE: str = "memory"
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "clouddesk_knowledge"

    # Business Rules & Tool Policy
    APPROVAL_REQUIRED_FOR_REFUNDS: bool = True
    MAX_REFUND_WITHOUT_APPROVAL: float = 0.0
    TOOL_TIMEOUT_SECONDS: int = 30
    SAMPLE_DATA_DIR: str = "./sample_data"

    # Observability & Tracing
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str = "clouddesk-support"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value]
        return value

    @property
    def effective_jwt_secret(self) -> str:
        """Returns SUPABASE_JWT_SECRET if configured, otherwise falls back to JWT_SECRET."""
        return self.SUPABASE_JWT_SECRET or self.JWT_SECRET

    @property
    def is_fake_redis(self) -> bool:
        """Returns True if fake Redis is forced or no Redis URL is provided."""
        return self.USE_FAKE_REDIS or not bool(self.REDIS_URL)


@lru_cache
def get_settings() -> Settings:
    """Returns cached Settings instance. Server must be restarted after .env changes."""
    return Settings()
