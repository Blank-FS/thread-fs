# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import embed

from app.core.config import settings
from app.db.init_db import reset_db, seed_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT == "production" and settings.DB_CREATE_DROP:
        raise RuntimeError("DB_CREATE_DROP should not be enabled in production")
    if settings.ENVIRONMENT == "development" and settings.DB_CREATE_DROP:
        await reset_db()
        await seed_db()

    yield


app = FastAPI(
    title="ThreadFS API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-ThreadFS-Community-Key",
    ],
    expose_headers=["Retry-After"],
)

app.include_router(embed.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
