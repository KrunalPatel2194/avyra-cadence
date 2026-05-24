"""JWT issuance + verification for mobile bearer auth.

Token payload (HS256, signed with JWT_SECRET):
    {
      "sub": "<user uuid>",
      "email": "...",
      "iat": <unix>,
      "exp": <unix>
    }

Mobile sends `Authorization: Bearer <jwt>` on every request after sign-in.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Header
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import User
from db.session import get_session

logger = logging.getLogger("cadence.security.jwt")

ALGO = "HS256"


def issue(user_id: uuid.UUID, email: str) -> str:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET not set — refusing to issue tokens")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.JWT_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGO)


def decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {e}") from e


async def current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    """FastAPI dependency. Verifies JWT, loads + returns the User row."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(None, 1)[1].strip()
    payload = decode(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="token missing sub")
    try:
        user_id = uuid.UUID(sub)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="invalid sub") from e
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="user no longer exists")
    return user
