"""Emails routes — paginated feed + detail.

Endpoints (all require Bearer JWT):
  GET  /emails?cursor=<iso8601>&limit=50   — most recent first
  GET  /emails/{id}                         — full body + summary + extracted tasks

Cursor is the `received_at` of the last item in the previous page (ISO 8601).
Stable under inserts because we order by received_at DESC, id DESC.

POST /emails/refresh lives here too — fires the Gmail watcher for this user
out-of-cycle. Actual watcher implementation lands in Step 8; this endpoint
is exposed now so the mobile pull-to-refresh has a real target to call.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Email, Task, User
from db.session import get_session
from gmail.watcher import poll_user
from security.jwt import current_user

logger = logging.getLogger("cadence.routes.emails")

router = APIRouter(prefix="/emails", tags=["emails"])


# ── Pydantic shapes ─────────────────────────────────────────────────────────
class EmailListItem(BaseModel):
    id: uuid.UUID
    gmail_msg_id: str
    from_addr: str
    subject: str
    received_at: datetime
    summary: str | None
    is_urgent: bool
    category: str | None
    task_count: int
    processed: bool


class EmailListResponse(BaseModel):
    items: list[EmailListItem]
    # ISO 8601 timestamp of the oldest item in this page — pass back as `cursor`
    # to get the next page. Null when there are no more results.
    next_cursor: str | None


class EmailDetail(BaseModel):
    id: uuid.UUID
    gmail_msg_id: str
    gmail_thread_id: str | None
    from_addr: str
    subject: str
    snippet: str
    body_text: str
    received_at: datetime
    summary: str | None
    is_urgent: bool
    category: str | None
    summary_model: str | None
    processed_at: datetime | None
    tasks: list[dict[str, Any]]


# ── Routes ──────────────────────────────────────────────────────────────────
@router.get("", response_model=EmailListResponse)
async def list_emails(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    cursor: str | None = Query(None, description="received_at of last item in previous page (ISO 8601)"),
    limit: int = Query(50, ge=1, le=100),
):
    stmt = select(Email).where(Email.user_id == user.id)
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"bad cursor: {e}")
        stmt = stmt.where(Email.received_at < cursor_dt)
    stmt = stmt.order_by(Email.received_at.desc(), Email.id.desc()).limit(limit)
    emails = (await session.scalars(stmt)).all()

    # Count tasks per email in one shot (skip soft-deleted).
    task_counts: dict[uuid.UUID, int] = {}
    if emails:
        email_ids = [e.id for e in emails]
        count_stmt = (
            select(Task.source_ref, func.count(Task.id))
            .where(
                and_(
                    Task.user_id == user.id,
                    Task.source_type == "email",
                    Task.source_ref.in_(email_ids),
                    Task.status != "deleted",
                )
            )
            .group_by(Task.source_ref)
        )
        for source_ref, count in (await session.execute(count_stmt)).all():
            task_counts[source_ref] = int(count)

    items = [
        EmailListItem(
            id=e.id,
            gmail_msg_id=e.gmail_msg_id,
            from_addr=e.from_addr,
            subject=e.subject,
            received_at=e.received_at,
            summary=e.summary,
            is_urgent=e.is_urgent,
            category=e.category,
            task_count=task_counts.get(e.id, 0),
            processed=e.processed_at is not None,
        )
        for e in emails
    ]

    next_cursor = emails[-1].received_at.isoformat() if len(emails) == limit else None
    return EmailListResponse(items=items, next_cursor=next_cursor)


@router.get("/{email_id}", response_model=EmailDetail)
async def get_email(
    email_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    e = await session.scalar(select(Email).where(and_(Email.id == email_id, Email.user_id == user.id)))
    if e is None:
        raise HTTPException(status_code=404, detail="email not found")

    task_rows = (
        await session.scalars(
            select(Task)
            .where(
                and_(
                    Task.user_id == user.id,
                    Task.source_type == "email",
                    Task.source_ref == email_id,
                    Task.status != "deleted",
                )
            )
            .order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
        )
    ).all()

    tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "due_time": t.due_time.isoformat() if t.due_time else None,
            "priority": t.priority,
            "status": t.status,
            "confidence": t.confidence,
            "rationale": t.rationale,
        }
        for t in task_rows
    ]

    return EmailDetail(
        id=e.id,
        gmail_msg_id=e.gmail_msg_id,
        gmail_thread_id=e.gmail_thread_id,
        from_addr=e.from_addr,
        subject=e.subject,
        snippet=e.snippet,
        body_text=e.body_text,
        received_at=e.received_at,
        summary=e.summary,
        is_urgent=e.is_urgent,
        category=e.category,
        summary_model=e.summary_model,
        processed_at=e.processed_at,
        tasks=tasks,
    )


@router.post("/refresh", status_code=202)
async def force_refresh(
    background: BackgroundTasks,
    user: User = Depends(current_user),
):
    """Pull-to-refresh: trigger an out-of-cycle Gmail poll for this user.

    Fires the watcher in the background and returns 202 immediately so the
    mobile UI never hangs. The watcher's per-user lock dedupes against the
    scheduled 2h tick so we never double-ingest.
    """
    if user.google_refresh_token_enc is None:
        raise HTTPException(status_code=409, detail="gmail not linked — sign in first")
    background.add_task(poll_user, user.id)
    logger.info("manual refresh queued user=%s", user.id)
    return {"queued": True, "user_id": str(user.id)}
