"""Gmail watcher — fetches new mail for a user and ingests via ai-engine.

Public entry point: `await poll_user(user_id)`.

Per-user pipeline:
    1. Load user + decrypt refresh token
    2. Run Gmail fetch (in a thread — google-api-python-client is sync)
       using `since = max(last_polled_at, now-24h)`
    3. For each new message:
         a. INSERT into emails (ON CONFLICT DO NOTHING via the unique constraint)
         b. Call ai-engine /api/cadence/summarize → store summary
         c. Call ai-engine /api/cadence/extract_tasks → insert tasks (email-source)
    4. Stamp users.last_polled_at = max(received_at) so the next run picks up
       precisely where this one left off.

Concurrency:
    One user at a time per process — guarded by a per-user asyncio.Lock so that
    a scheduled tick and a manual /emails/refresh don't double-ingest. The
    scheduler (Step 9) iterates users serially; if we ever need parallel users,
    swap the in-process lock for a Redis advisory lock or Postgres SELECT FOR
    UPDATE SKIP LOCKED.

Skipping rules:
    Promotional / forum-category messages get stored but are NOT sent to the
    LLM. Wasting Ollama cycles summarizing Macy's emails is a net negative.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Email, Task, User
from db.session import db_session
from gmail.client import GmailMessage, fetch_new_messages_sync
from llm.ai_engine_client import AiEngineError, get_client
from security.crypto import decrypt

logger = logging.getLogger("cadence.gmail.watcher")

_user_locks: dict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)


async def poll_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Run one ingestion pass for a single user.

    Returns a small dict with counters — handy for /emails/refresh and the
    scheduler log line. Never raises on per-message errors; logs and continues.
    Top-level errors (auth failure, ai-engine down) DO raise so the caller can
    surface them.
    """
    lock = _user_locks[user_id]
    if lock.locked():
        logger.info("poll_user(%s): another poll in progress, skipping", user_id)
        return {"skipped": True, "reason": "in_progress"}

    async with lock:
        async with db_session() as session:
            user = await session.scalar(select(User).where(User.id == user_id))
            if user is None:
                return {"skipped": True, "reason": "user_not_found"}
            if user.google_refresh_token_enc is None:
                return {"skipped": True, "reason": "gmail_not_linked"}

            refresh_token = decrypt(bytes(user.google_refresh_token_enc))
            since = user.last_polled_at
            user_email = user.email
            user_tz = user.tz
            poll_started = datetime.now(timezone.utc)

        # Fetch outside the DB transaction — the Gmail call can take seconds.
        try:
            messages = await asyncio.to_thread(
                fetch_new_messages_sync, refresh_token, since=since
            )
        except Exception as e:
            logger.error("gmail fetch failed user=%s: %s", user_id, e)
            raise

        if not messages:
            async with db_session() as session:
                u = await session.scalar(select(User).where(User.id == user_id))
                if u:
                    u.last_polled_at = poll_started
            return {"new": 0, "summarized": 0, "tasks": 0}

        new_count = 0
        summarized_count = 0
        tasks_count = 0
        client = get_client()

        for msg in messages:
            try:
                email_id, was_new = await _upsert_email(user_id, msg)
            except Exception as e:
                logger.warning("upsert failed user=%s msg=%s: %s", user_id, msg.msg_id, e)
                continue
            if not was_new:
                continue
            new_count += 1

            if msg.is_promo:
                # Stored but not LLM-processed; mark processed so we don't try later.
                await _mark_processed(email_id, summary=None, model=None, urgent=False, category="promo")
                continue

            # Summarize + extract_tasks via ai-engine.
            try:
                sum_resp = await client.summarize(
                    source_type="email",
                    source_id=str(email_id),
                    from_addr=msg.from_addr or msg.from_name,
                    subject=msg.subject,
                    received_at=msg.received_at,
                    body=msg.body_text,
                )
                await _mark_processed(
                    email_id,
                    summary=sum_resp.get("summary"),
                    model=sum_resp.get("model"),
                    urgent=bool(sum_resp.get("is_urgent")),
                    category=sum_resp.get("category") or "other",
                )
                summarized_count += 1
            except AiEngineError as e:
                logger.warning("summarize failed email=%s: %s", email_id, e)
                # Leave processed_at NULL so a later run can retry.
                continue

            try:
                ext_resp = await client.extract_tasks(
                    source_type="email",
                    source_id=str(email_id),
                    from_addr=msg.from_addr or msg.from_name,
                    subject=msg.subject,
                    received_at=msg.received_at,
                    user_tz=user_tz,
                    body=msg.body_text,
                )
                added = await _insert_tasks(
                    user_id, email_id, ext_resp.get("tasks") or [], ext_resp.get("model")
                )
                tasks_count += added
            except AiEngineError as e:
                logger.warning("extract_tasks failed email=%s: %s", email_id, e)

        # Bump the watermark to the newest message's received_at (or poll_started
        # if no new messages survived). We pick the *newest* successfully-fetched
        # received_at — not poll_started — so a server-clock skew can't cause us
        # to miss messages.
        watermark = max(m.received_at for m in messages)
        async with db_session() as session:
            u = await session.scalar(select(User).where(User.id == user_id))
            if u:
                u.last_polled_at = max(watermark, poll_started)

        logger.info(
            "poll_user(%s) done: new=%d summarized=%d tasks=%d email=%s",
            user_id, new_count, summarized_count, tasks_count, user_email,
        )
        return {"new": new_count, "summarized": summarized_count, "tasks": tasks_count}


# ── Internal helpers ────────────────────────────────────────────────────────
async def _upsert_email(user_id: uuid.UUID, msg: GmailMessage) -> tuple[uuid.UUID, bool]:
    """Insert email if new; return (email_id, was_new). Idempotent on
    (user_id, gmail_msg_id) thanks to the unique constraint."""
    async with db_session() as session:
        stmt = (
            pg_insert(Email)
            .values(
                user_id=user_id,
                gmail_msg_id=msg.msg_id,
                gmail_thread_id=msg.thread_id,
                from_addr=msg.from_addr,
                subject=msg.subject,
                snippet=msg.snippet,
                body_text=msg.body_text,
                received_at=msg.received_at,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "gmail_msg_id"])
            .returning(Email.id)
        )
        result = await session.execute(stmt)
        row = result.first()
        if row is not None:
            return row[0], True

        # Row already existed — fetch its id.
        existing = await session.scalar(
            select(Email.id).where(
                Email.user_id == user_id, Email.gmail_msg_id == msg.msg_id
            )
        )
        return existing, False  # type: ignore[return-value]


async def _mark_processed(
    email_id: uuid.UUID,
    *,
    summary: str | None,
    model: str | None,
    urgent: bool,
    category: str | None,
) -> None:
    async with db_session() as session:
        e = await session.scalar(select(Email).where(Email.id == email_id))
        if e is None:
            return
        e.summary = summary
        e.summary_model = model
        e.is_urgent = urgent
        e.category = category
        e.processed_at = datetime.now(timezone.utc)


async def _insert_tasks(
    user_id: uuid.UUID,
    email_id: uuid.UUID,
    raw_tasks: list[dict[str, Any]],
    model: str | None,
) -> int:
    """Insert LLM-extracted tasks. Skips ones that already exist (idempotent
    by title + source_ref) so a re-run of the same email doesn't duplicate."""
    if not raw_tasks:
        return 0
    from datetime import date as _date, time as _time

    inserted = 0
    async with db_session() as session:
        # Existing titles for this email — cheap dedupe key.
        existing_titles = {
            row.title
            for row in (
                await session.scalars(
                    select(Task).where(Task.source_type == "email", Task.source_ref == email_id)
                )
            ).all()
        }

        for t in raw_tasks:
            title = (t.get("title") or "").strip()
            if not title or title in existing_titles:
                continue

            due_date = None
            if isinstance(t.get("due_date"), str):
                try:
                    due_date = _date.fromisoformat(t["due_date"])
                except ValueError:
                    due_date = None

            due_time = None
            if isinstance(t.get("due_time"), str):
                try:
                    due_time = _time.fromisoformat(t["due_time"])
                except ValueError:
                    due_time = None

            priority = t.get("priority") if t.get("priority") in ("low", "med", "high") else "low"
            confidence = float(t.get("confidence") or 0.0)
            # Low-confidence tasks survive but stay 'snoozed' — they show up
            # in the "suggested" filter rather than the main list.
            status = "snoozed" if confidence < 0.55 else "open"

            row = Task(
                user_id=user_id,
                source_type="email",
                source_ref=email_id,
                title=title[:200],
                due_date=due_date,
                due_time=due_time,
                priority=priority,
                status=status,
                confidence=confidence,
                rationale=(t.get("rationale") or "")[:500],
                extracted_model=model,
            )
            session.add(row)
            inserted += 1
            existing_titles.add(title)

    return inserted
