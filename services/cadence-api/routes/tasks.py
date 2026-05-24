"""Tasks routes — unified list across email/news/manual sources.

Endpoints (all require Bearer JWT):
  GET    /tasks?status=open|done|snoozed&due=today|week|overdue|all&source=all|email|news|manual&limit=200
  POST   /tasks                 — create a manual task
  PATCH  /tasks/{id}            — partial update (status, fields)
  DELETE /tasks/{id}            — hard-delete manual; soft-delete LLM-extracted (status='deleted')

Manual tasks: source_type='manual', source_ref=null. They use the same row and
the same notification path as LLM-extracted ones.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date as date_cls, datetime, time as time_cls, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Task, User
from db.session import get_session
from security.jwt import current_user

logger = logging.getLogger("cadence.routes.tasks")

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── Pydantic shapes ─────────────────────────────────────────────────────────
SourceType = Literal["email", "news", "manual"]
Priority = Literal["low", "med", "high"]
Status = Literal["open", "done", "snoozed", "deleted"]


class TaskOut(BaseModel):
    id: uuid.UUID
    source_type: SourceType
    source_ref: uuid.UUID | None
    title: str
    notes: str
    due_date: date_cls | None
    due_time: time_cls | None
    remind_at: datetime | None
    priority: Priority
    status: Status
    confidence: float | None
    rationale: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    """Manual task creation. source_type is forced to 'manual' server-side."""
    title: str = Field(min_length=1, max_length=200)
    notes: str = ""
    due_date: date_cls | None = None
    due_time: time_cls | None = None
    remind_at: datetime | None = None
    priority: Priority = "low"

    @field_validator("notes")
    @classmethod
    def _trim_notes(cls, v: str) -> str:
        return (v or "").strip()[:4000]


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    due_date: date_cls | None = None
    due_time: time_cls | None = None
    remind_at: datetime | None = None
    priority: Priority | None = None
    status: Status | None = None


def _to_out(t: Task) -> TaskOut:
    return TaskOut(
        id=t.id,
        source_type=t.source_type,          # type: ignore[arg-type]
        source_ref=t.source_ref,
        title=t.title,
        notes=t.notes,
        due_date=t.due_date,
        due_time=t.due_time,
        remind_at=t.remind_at,
        priority=t.priority,                # type: ignore[arg-type]
        status=t.status,                    # type: ignore[arg-type]
        confidence=t.confidence,
        rationale=t.rationale,
        completed_at=t.completed_at,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


# ── Routes ──────────────────────────────────────────────────────────────────
@router.get("", response_model=list[TaskOut])
async def list_tasks(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    status: Literal["open", "done", "snoozed", "all"] = Query("open"),
    due: Literal["today", "week", "overdue", "all"] = Query("all"),
    source: Literal["email", "news", "manual", "all"] = Query("all"),
    limit: int = Query(200, ge=1, le=500),
):
    stmt = select(Task).where(Task.user_id == user.id)

    if status == "all":
        # Still hide soft-deleted from the unified list.
        stmt = stmt.where(Task.status != "deleted")
    else:
        stmt = stmt.where(Task.status == status)

    if source != "all":
        stmt = stmt.where(Task.source_type == source)

    today = datetime.now(timezone.utc).date()
    if due == "today":
        stmt = stmt.where(Task.due_date == today)
    elif due == "week":
        stmt = stmt.where(and_(Task.due_date >= today, Task.due_date <= today + timedelta(days=7)))
    elif due == "overdue":
        stmt = stmt.where(and_(Task.due_date.is_not(None), Task.due_date < today, Task.status == "open"))

    # Order: open & dated first (by due_date asc), then undated, then completed.
    stmt = stmt.order_by(
        Task.status.asc(),
        Task.due_date.asc().nulls_last(),
        Task.priority.desc(),
        Task.created_at.desc(),
    ).limit(limit)

    rows = (await session.scalars(stmt)).all()
    return [_to_out(t) for t in rows]


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    body: TaskCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    t = Task(
        user_id=user.id,
        source_type="manual",
        source_ref=None,
        title=body.title.strip()[:200],
        notes=body.notes,
        due_date=body.due_date,
        due_time=body.due_time,
        remind_at=body.remind_at,
        priority=body.priority,
        status="open",
    )
    session.add(t)
    await session.flush()
    logger.info("manual task created user=%s task=%s", user.id, t.id)
    return _to_out(t)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID,
    body: TaskPatch,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    t = await session.scalar(select(Task).where(and_(Task.id == task_id, Task.user_id == user.id)))
    if t is None:
        raise HTTPException(status_code=404, detail="task not found")

    if body.title is not None:
        t.title = body.title.strip()[:200] or t.title
    if body.notes is not None:
        t.notes = body.notes.strip()[:4000]
    if body.due_date is not None or "due_date" in body.model_fields_set:
        t.due_date = body.due_date
    if body.due_time is not None or "due_time" in body.model_fields_set:
        t.due_time = body.due_time
    if body.remind_at is not None or "remind_at" in body.model_fields_set:
        t.remind_at = body.remind_at
    if body.priority is not None:
        t.priority = body.priority

    if body.status is not None and body.status != t.status:
        t.status = body.status
        if body.status == "done":
            t.completed_at = datetime.now(timezone.utc)
        elif body.status == "open":
            t.completed_at = None

    t.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return _to_out(t)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    t = await session.scalar(select(Task).where(and_(Task.id == task_id, Task.user_id == user.id)))
    if t is None:
        raise HTTPException(status_code=404, detail="task not found")

    if t.source_type == "manual":
        await session.delete(t)
    else:
        # LLM-extracted: soft-delete so the next ingestion run doesn't re-create
        # the same task from the same source email/news item.
        t.status = "deleted"
        t.updated_at = datetime.now(timezone.utc)

    return None
