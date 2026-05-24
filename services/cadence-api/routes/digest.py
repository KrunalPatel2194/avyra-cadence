"""Digest routes — fetch today's digest, force-generate."""
from __future__ import annotations

import uuid
from datetime import date as date_cls, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Digest, User
from db.session import get_session
from digest import generate_for_user
from security.jwt import current_user

router = APIRouter(prefix="/digest", tags=["digest"])


class DigestOut(BaseModel):
    id: uuid.UUID
    date: date_cls
    body_md: str
    highlights: list[str]
    generated_at: datetime
    delivered_at: datetime | None


def _user_local_date(user_tz: str) -> date_cls:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(user_tz)).date()
    except Exception:
        return datetime.now(timezone.utc).date()


@router.get("/today", response_model=DigestOut | None)
async def get_today(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    today = _user_local_date(user.tz)
    d = await session.scalar(
        select(Digest).where(and_(Digest.user_id == user.id, Digest.digest_date == today))
    )
    if d is None:
        return None
    return DigestOut(
        id=d.id, date=d.digest_date, body_md=d.body_md,
        highlights=list(d.highlights or []),
        generated_at=d.generated_at, delivered_at=d.delivered_at,
    )


@router.post("/generate", status_code=202)
async def trigger_generate(
    background: BackgroundTasks,
    user: User = Depends(current_user),
):
    background.add_task(generate_for_user, user.id)
    return {"queued": True}
