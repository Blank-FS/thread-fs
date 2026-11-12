# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    ENVIRONMENT: str = "development"
    DB_CREATE_DROP: bool = True

    # Shares rate limits between workers. Without it each worker counts for itself, which is fine for development
    REDIS_URL: str | None = None
    CORS_ALLOW_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Webhooks (app.services.webhook_service): the loop that sends queued events to communities' endpoints
    WEBHOOK_DELIVERY_ENABLED: bool = True
    WEBHOOK_POLL_SECONDS: float = 2.0
    # Development only: give the seeded demo community a webhook to this URL, e.g. the dev listener's
    # (python -m app.scripts.webhook_listener prints it)
    DEMO_WEBHOOK_URL: str | None = None

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_READ_PER_MINUTE: int = 120
    RATE_LIMIT_COMMENT_CREATE_PER_MINUTE: int = 5
    RATE_LIMIT_COMMENT_EDIT_PER_HOUR: int = 20
    RATE_LIMIT_COMMENT_DELETE_PER_HOUR: int = 20
    RATE_LIMIT_VOTE_PER_MINUTE: int = 60
    RATE_LIMIT_REPORT_PER_HOUR: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        if self.DATABASE_URL.startswith("sqlite+aiosqlite://"):
            return self.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://", 1)

        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL.replace(
                "postgresql+asyncpg://",
                "postgresql+psycopg://",
                1,
            )

        return self.DATABASE_URL

    @property
    def CORS_ALLOW_ORIGINS_LIST(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.CORS_ALLOW_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
