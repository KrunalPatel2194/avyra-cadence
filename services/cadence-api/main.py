"""Cadence-api — FastAPI entry point (port 8010).

Mobile-facing API for the Cadence iOS/Android app. Owns Gmail state, Postgres,
APNs, and the 2h poll scheduler. Delegates ALL LLM work to ai-engine's
`/api/cadence/*` routes (single-AI-architecture rule).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.init import bootstrap_schema
from routes.auth import router as auth_router
from routes.devices import router as devices_router
from routes.digest import router as digest_router
from routes.emails import router as emails_router
from routes.tasks import router as tasks_router
import scheduler as _scheduler

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cadence")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("cadence-api starting on port %d", settings.PORT)
    try:
        await bootstrap_schema()
    except Exception as e:
        # In dev we want a loud error but not a crash loop. Routes that need
        # the DB will fail fast on first request — easier to debug than a
        # silent restart cycle.
        logger.error("schema bootstrap failed: %s", e)
    try:
        await _scheduler.start()
    except Exception as e:
        logger.error("scheduler failed to start: %s", e)
    yield
    try:
        await _scheduler.stop()
    except Exception:
        pass
    logger.info("cadence-api shutting down")


app = FastAPI(
    title="Cadence API",
    description="Gmail summarization + task agent for the Cadence iOS/Android app.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(digest_router)
app.include_router(emails_router)
app.include_router(tasks_router)


@app.get("/health")
async def health():
    return {"ok": True, "service": settings.SERVICE_NAME}


@app.get("/ready")
async def ready():
    """Deeper check — verifies DB connectivity. Returns 503 if Postgres is down."""
    from sqlalchemy import text
    from db.session import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        return {"ok": False, "db": False, "error": str(e)[:200]}
    return {"ok": True, "db": True}
