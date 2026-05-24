"""Daily digest generator — assembles inputs, calls ai-engine, persists, notifies.

`generate_for_user(user_id, today_in_user_tz)` is idempotent on (user_id, date)
thanks to the unique constraint on digests — re-running the same day overwrites
the existing row instead of erroring.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date as date_cls, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Digest, Email, Task, User
from db.session import db_session
from llm.ai_engine_client import AiEngineError, get_client
from push.apns import send_to_user

logger = logging.getLogger("cadence.digest")


def _user_local_date(user_tz: str) -> date_cls:
    """Today in the user's IANA tz."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(user_tz)).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _email_to_summary(e: Email) -> dict[str, Any]:
    return {
        "subject": e.subject,
        "from": e.from_addr,
        "summary": e.summary or "",
        "category": e.category or "other",
        "is_urgent": e.is_urgent,
        "received_at": e.received_at.isoformat(),
    }


def _task_to_dict(t: Task) -> dict[str, Any]:
    return {
        "title": t.title,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "priority": t.priority,
        "source": t.source_type,
    }


async def generate_for_user(user_id: uuid.UUID) -> dict[str, Any]:
    async with db_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if user is None:
            return {"skipped": "user_not_found"}

        today = _user_local_date(user.tz)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        emails = (await session.scalars(
            select(Email)
            .where(and_(
                Email.user_id == user_id,
                Email.received_at >= cutoff,
                Email.processed_at.is_not(None),
                Email.summary.is_not(None),
            ))
            .order_by(Email.received_at.desc())
            .limit(40)
        )).all()

        open_tasks = (await session.scalars(
            select(Task)
            .where(and_(Task.user_id == user_id, Task.status == "open"))
            .order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
            .limit(40)
        )).all()

        overdue_tasks = [t for t in open_tasks if t.due_date and t.due_date < today]

        summaries = [_email_to_summary(e) for e in emails]
        open_dicts = [_task_to_dict(t) for t in open_tasks]
        overdue_dicts = [_task_to_dict(t) for t in overdue_tasks]
        user_name = user.name
        user_tz = user.tz

    try:
        client = get_client()
        resp = await client.digest(
            user_name=user_name,
            user_tz=user_tz,
            today=today.isoformat(),
            summaries=summaries,
            open_tasks=open_dicts,
            overdue_tasks=overdue_dicts,
        )
    except AiEngineError as e:
        logger.error("digest LLM failed user=%s: %s", user_id, e)
        return {"error": str(e)}

    body_md = resp.get("digest") or "Inbox is quiet and nothing's due today."
    highlights = resp.get("highlights") or []
    model = resp.get("model")

    async with db_session() as session:
        stmt = (
            pg_insert(Digest)
            .values(
                user_id=user_id,
                digest_date=today,
                body_md=body_md,
                highlights=highlights,
                generated_model=model,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "digest_date"],
                set_={"body_md": body_md, "highlights": highlights, "generated_model": model,
                      "generated_at": datetime.now(timezone.utc)},
            )
        )
        await session.execute(stmt)

        # Push notification (best-effort).
        first_highlight = (highlights[0] if highlights else "Your morning briefing is ready.")
        try:
            await send_to_user(
                session,
                user_id,
                title=f"Cadence — {today.isoformat()}",
                body=first_highlight[:120],
                category="digest",
                payload={"kind": "digest", "date": today.isoformat()},
            )
        except Exception as e:
            logger.warning("digest push failed user=%s: %s", user_id, e)

        # Mark delivered_at on the row we just wrote.
        d = await session.scalar(
            select(Digest).where(and_(Digest.user_id == user_id, Digest.digest_date == today))
        )
        if d is not None:
            d.delivered_at = datetime.now(timezone.utc)

    return {"ok": True, "date": today.isoformat(), "highlights": len(highlights)}
