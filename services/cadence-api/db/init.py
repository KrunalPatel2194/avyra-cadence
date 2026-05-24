"""Bootstrap helper — runs db/schema.sql against the configured Postgres on startup.

Idempotent (schema.sql uses IF NOT EXISTS). For v1 we skip alembic; once we
need column changes against live data, swap this for proper migrations.
"""
from __future__ import annotations

import logging
from pathlib import Path

from db.session import engine

logger = logging.getLogger("cadence.db.init")

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def bootstrap_schema() -> None:
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with engine.begin() as conn:
        # asyncpg's exec_driver_sql handles multi-statement scripts via the raw conn.
        raw = await conn.get_raw_connection()
        # SQLAlchemy 2.0 wraps the asyncpg connection — drill down to it.
        underlying = raw.driver_connection
        await underlying.execute(sql)
    logger.info("schema bootstrap complete (%s)", _SCHEMA_PATH.name)
