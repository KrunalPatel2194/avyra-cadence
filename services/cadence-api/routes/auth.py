"""Auth routes — POST /auth/google/exchange + GET /me.

Exchange flow:
    RN app  --PKCE auth--> Google
                          (browser returns: code + code_verifier)
    RN app  --POST /auth/google/exchange { code, code_verifier, redirect_uri }-->  cadence-api
                          - validate id_token, ensure gmail scope granted
                          - upsert User by email; encrypt + store refresh_token
                          - issue our own JWT (HS256, 30d)
    RN app  <--{ jwt, user }--  cadence-api

On re-auth, Google may omit refresh_token. We only overwrite if a new
refresh_token actually arrives — never null out a working token.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import User
from db.session import get_session
from gmail.oauth import exchange_code
from security.crypto import encrypt
from security.jwt import current_user, issue as issue_jwt

logger = logging.getLogger("cadence.routes.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / response models ───────────────────────────────────────────────
class ExchangeRequest(BaseModel):
    code: str = Field(min_length=1)
    code_verifier: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)
    tz: str | None = None  # optional client-provided IANA tz on first sign-in


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    tz: str
    gmail_linked: bool


class ExchangeResponse(BaseModel):
    jwt: str
    user: UserOut


# ── Routes ──────────────────────────────────────────────────────────────────
@router.post("/google/exchange", response_model=ExchangeResponse)
async def google_exchange(
    req: ExchangeRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        tokens = await exchange_code(
            code=req.code,
            code_verifier=req.code_verifier,
            redirect_uri=req.redirect_uri,
        )
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    user = await session.scalar(select(User).where(User.email == tokens.email))
    if user is None:
        user = User(
            email=tokens.email,
            name=tokens.name or "",
            tz=req.tz or "America/Toronto",
        )
        session.add(user)
        await session.flush()
        logger.info("created user %s (%s)", user.id, user.email)
    else:
        # Refresh display name + tz if the client provided one; never silently
        # downgrade tz to default.
        if tokens.name and not user.name:
            user.name = tokens.name
        if req.tz:
            user.tz = req.tz

    # Only persist a refresh token if Google actually returned one. Google
    # omits it on re-consent; in that case we keep the existing encrypted
    # value (and the user remains linked).
    if tokens.refresh_token:
        user.google_refresh_token_enc = encrypt(tokens.refresh_token)
        logger.info("updated refresh token for %s", user.email)
    elif user.google_refresh_token_enc is None:
        # First sign-in but Google returned no refresh token — almost always
        # means the consent screen was bypassed. Force the client to retry
        # with prompt=consent.
        raise HTTPException(
            status_code=400,
            detail="google did not return refresh_token — sign in with prompt=consent",
        )

    await session.flush()

    token_jwt = issue_jwt(user.id, user.email)
    return ExchangeResponse(
        jwt=token_jwt,
        user=UserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            tz=user.tz,
            gmail_linked=user.google_refresh_token_enc is not None,
        ),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        tz=user.tz,
        gmail_linked=user.google_refresh_token_enc is not None,
    )


class DevLoginRequest(BaseModel):
    email: EmailStr
    name: str = ""
    tz: str | None = None


@router.post("/dev-login", response_model=ExchangeResponse)
async def dev_login(
    req: DevLoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Backdoor for local dev — issues a JWT for any email, no Google needed.
    Gated by DEV_LOGIN_ENABLED. Use this in Expo Go where real iOS OAuth
    cannot redirect. Gmail features stay dormant (no refresh token) but the
    rest of the app works end-to-end."""
    if not settings.DEV_LOGIN_ENABLED:
        raise HTTPException(status_code=404, detail="not found")

    email = req.email.lower()
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=req.name or email.split("@")[0], tz=req.tz or "America/Toronto")
        session.add(user)
        await session.flush()
        logger.info("dev-login created user %s", email)
    else:
        if req.tz:
            user.tz = req.tz

    token_jwt = issue_jwt(user.id, user.email)
    return ExchangeResponse(
        jwt=token_jwt,
        user=UserOut(
            id=user.id, email=user.email, name=user.name, tz=user.tz,
            gmail_linked=user.google_refresh_token_enc is not None,
        ),
    )


@router.post("/revoke")
async def revoke(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    """Drop the stored refresh token. App should also call Google's revoke
    endpoint client-side if it wants the consent screen to reappear next time."""
    user.google_refresh_token_enc = None
    user.gmail_history_id = None
    session.add(user)
    return {"ok": True, "gmail_linked": False}
