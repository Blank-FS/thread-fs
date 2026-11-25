# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    ENVIRONMENT: str = "development"
    DB_CREATE_DROP: bool = True

    # Shares rate limits between workers. Without it each worker counts for itself, which is fine for development
    REDIS_URL: str | None = None

    # Database connections, per worker: workers x (size + overflow) must fit in the database's max_connections
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5
    # How long a request waits for one before failing. Under too much load, failing beats an ever longer queue
    DB_POOL_TIMEOUT_SECONDS: float = 10

    # How long each worker remembers a community's settings, origins, keys and reasons, and so how long a change to them
    # can take to apply (app.services.community_context). 0 reads them for every request
    COMMUNITY_CACHE_SECONDS: float = 30
    # How long readers of the same thread share its pages: how old they can be signed out, and vote counts signed in
    # (app.services.comment_page_service). 0 turns it off
    READ_CACHE_SECONDS: float = 5
    CORS_ALLOW_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Webhooks (app.services.webhook_service): the loop that sends queued events to communities' endpoints
    WEBHOOK_DELIVERY_ENABLED: bool = True
    WEBHOOK_POLL_SECONDS: float = 2.0
    # Development only: give the seeded demo community a webhook to this URL, e.g. the dev listener's
    # (python -m app.scripts.webhook_listener prints it)
    DEMO_WEBHOOK_URL: str | None = None
    # Development only: turn GIFs on in the seeded demo community with this KLIPY app key (app.core.gifs)
    DEMO_KLIPY_APP_KEY: str | None = None

    # Characters of markdown in one comment. The widget learns it from the community's config
    MAX_COMMENT_LENGTH: int = 10_000

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
