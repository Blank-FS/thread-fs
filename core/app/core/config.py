# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    ENVIRONMENT: str = "development"
    DB_CREATE_DROP: bool = True

    CORS_ALLOW_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_READ_PER_MINUTE: int = 120
    RATE_LIMIT_COMMENT_CREATE_PER_MINUTE: int = 5
    RATE_LIMIT_COMMENT_EDIT_PER_HOUR: int = 20
    RATE_LIMIT_COMMENT_DELETE_PER_HOUR: int = 20
    RATE_LIMIT_VOTE_PER_MINUTE: int = 60

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
