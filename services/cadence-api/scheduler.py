"""APScheduler — drives the four background jobs cadence-api owns.

Jobs:
  * gmail_poll_all   — every GMAIL_POLL_INTERVAL_SECONDS (default 2h).
                       Iterates users with linked Gmail and runs poll_user(uid).
  * digest_tick      — every 5 minutes. Generates today's digest for each user
                       whose local hour just hit digest_hour_local and who
                       doesn't yet have a row in digests for today.
  * overdue_sweep    — every OVERDUE_SWEEP_INTERVAL_SECONDS (default 1h).
                       Sends an APNs nudge for any task that became overdue
                       since the last sweep (reminded_at NULL guards re-spam).
  * reminder_tick    — every 60s. Fires APNs for tasks whose remind_at has
                       arrived and reminded_at is still NULL.

The scheduler starts on FastAPI lifespan startup and stops cleanly on shutdown.
All jobs are wrapped in try/except so one bad user can't kill the loop.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date as date_cls, datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_, select

from config import settings
from db.models import Digest, Task, User
from db.session import db_session
from digest import generate_for_user
from gmail.watcher import poll_user
from push.apns import send_to_user

logger = logging.getLogger("cadence.scheduler")

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


# ── Jobs ────────────────────────────────────────────────────────────────────
async def gmail_poll_all() -> None:
    async with db_session() as session:
        user_ids = (await session.scalars(
            select(User.id).where(User.google_refresh_token_enc.is_not(None))
        )).all()

    if not user_ids:
        return
    logger.info("gmail_poll_all: %d user(s)", len(user_ids))
    for uid in user_ids:
        try:
            await poll_user(uid)
        except Exception as e:
            logger.warning("poll_user(%s) raised: %s", uid, e)


def _local_hour(tz: str) -> int:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz)).hour
    except Exception:
        return datetime.now(timezone.utc).hour


def _local_date(tz: str) -> date_cls:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz)).date()
    except Exception:
        return datetime.now(timezone.utc).date()


async def digest_tick() -> None:
    async with db_session() as session:
        users = (await session.scalars(select(User))).all()
    if not users:
        return
    for u in users:
        if _local_hour(u.tz) != int(u.digest_hour_local):
            continue
        today = _local_date(u.tz)
        async with db_session() as session:
            existing = await session.scalar(
                select(Digest).where(and_(Digest.user_id == u.id, Digest.digest_date == today))
            )
        if existing is not None:
            continue
        try:
            await generate_for_user(u.id)
        except Exception as e:
            logger.warning("digest generate user=%s: %s", u.id, e)


async def overdue_sweep() -> None:
    """Send one APNs nudge per newly-overdue task. reminded_at guards repeats."""
    async with db_session() as session:
        users = (await session.scalars(select(User))).all()
    for u in users:
        today = _local_date(u.tz)
        async with db_session() as session:
            rows = (await session.scalars(
                select(Task).where(and_(
                    Task.user_id == u.id,
                    Task.status == "open",
                    Task.due_date.is_not(None),
                    Task.due_date < today,
                    Task.reminded_at.is_(None),
                ))
            )).all()
            for t in rows:
                try:
                    await send_to_user(
                        session, u.id,
                        title="Overdue task",
                        body=t.title[:120],
                        category="overdue",
                        payload={"kind": "overdue", "task_id": str(t.id)},
                    )
                    t.reminded_at = datetime.now(timezone.utc)
                except Exception as e:
                    logger.warning("overdue push user=%s task=%s: %s", u.id, t.id, e)


async def reminder_tick() -> None:
    now = datetime.now(timezone.utc)
    async with db_session() as session:
        rows = (await session.scalars(
            select(Task).where(and_(
                Task.status == "open",
                Task.remind_at.is_not(None),
                Task.remind_at <= now,
                Task.reminded_at.is_(None),
            ))
        )).all()
        for t in rows:
            try:
                await send_to_user(
                    session, t.user_id,
                    title="Reminder",
                    body=t.title[:120],
                    category="reminder",
                    payload={"kind": "reminder", "task_id": str(t.id)},
                )
                t.reminded_at = now
            except Exception as e:
                logger.warning("reminder push task=%s: %s", t.id, e)


# ── Lifecycle ───────────────────────────────────────────────────────────────
async def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        gmail_poll_all,
        IntervalTrigger(seconds=settings.GMAIL_POLL_INTERVAL_SECONDS),
        id="gmail_poll_all", coalesce=True, max_instances=1,
        next_run_time=datetime.now(timezone.utc),     # first run on startup
    )
    _scheduler.add_job(
        digest_tick,
        IntervalTrigger(seconds=300),
        id="digest_tick", coalesce=True, max_instances=1,
    )
    _scheduler.add_job(
        overdue_sweep,
        IntervalTrigger(seconds=settings.OVERDUE_SWEEP_INTERVAL_SECONDS),
        id="overdue_sweep", coalesce=True, max_instances=1,
    )
    _scheduler.add_job(
        reminder_tick,
        IntervalTrigger(seconds=60),
        id="reminder_tick", coalesce=True, max_instances=1,
    )
    _scheduler.start()
    logger.info(
        "scheduler started: gmail_poll_all=%ds, digest_tick=300s, overdue_sweep=%ds, reminder_tick=60s",
        settings.GMAIL_POLL_INTERVAL_SECONDS, settings.OVERDUE_SWEEP_INTERVAL_SECONDS,
    )


async def stop() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("scheduler stopped")
