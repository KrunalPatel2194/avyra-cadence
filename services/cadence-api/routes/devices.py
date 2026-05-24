"""Devices routes — register / unregister push tokens."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Device, User
from db.session import get_session
from security.jwt import current_user

logger = logging.getLogger("cadence.routes.devices")

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceRegister(BaseModel):
    platform: Literal["ios", "android"]
    push_token: str = Field(min_length=8, max_length=512)


@router.post("", status_code=201)
async def register_device(
    body: DeviceRegister,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # Upsert on (user_id, push_token).
    stmt = (
        pg_insert(Device)
        .values(user_id=user.id, platform=body.platform, push_token=body.push_token,
                last_seen_at=datetime.now(timezone.utc))
        .on_conflict_do_update(
            index_elements=["user_id", "push_token"],
            set_={"last_seen_at": datetime.now(timezone.utc), "platform": body.platform},
        )
        .returning(Device.id)
    )
    result = await session.execute(stmt)
    device_id = result.scalar()
    return {"ok": True, "device_id": str(device_id)}


@router.delete("/{push_token}", status_code=204)
async def unregister_device(
    push_token: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    d = await session.scalar(
        select(Device).where(and_(Device.user_id == user.id, Device.push_token == push_token))
    )
    if d is None:
        raise HTTPException(status_code=404, detail="device not registered")
    await session.delete(d)
    return None
