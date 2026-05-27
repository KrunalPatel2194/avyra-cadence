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

import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import User
from db.session import get_session
from gmail.oauth import exchange_code
from gmail.web_oauth import (
    build_authorize_url,
    decode_state,
    encode_state,
    exchange_code_web,
    is_allowed_return_to,
)
from gmail.oauth import GoogleTokens  # noqa: F401  (kept for type continuity)
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


class NativeExchangeRequest(BaseModel):
    server_auth_code: str = Field(min_length=1)
    tz: str | None = None


@router.post("/google/native-exchange", response_model=ExchangeResponse)
async def google_native_exchange(
    req: NativeExchangeRequest,
    session: AsyncSession = Depends(get_session),
):
    """Mobile calls this after the native Google Sign-In SDK returns a
    serverAuthCode. We exchange with the Web client (redirect_uri="" because
    no redirect happened) and issue our JWT.

    Requires GOOGLE_WEB_CLIENT_ID + GOOGLE_WEB_CLIENT_SECRET in env."""
    try:
        # Native SDK serverAuthCode → empty redirect_uri.
        tokens = await exchange_code_web(req.server_auth_code, redirect_uri="")
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
        if tokens.name and not user.name:
            user.name = tokens.name
        if req.tz:
            user.tz = req.tz

    if tokens.refresh_token:
        user.google_refresh_token_enc = encrypt(tokens.refresh_token)
        logger.info("updated refresh token for %s", user.email)
    elif user.google_refresh_token_enc is None:
        raise HTTPException(
            status_code=400,
            detail="google did not return refresh_token — sign in again with prompt=consent",
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


@router.get("/google/start")
async def google_start(return_to: str = Query(..., description="deep link to send the JWT back to")):
    """Mobile opens this URL in a WebBrowser. We redirect to Google with a
    signed `state` carrying the deep-link to return to after the callback."""
    if not is_allowed_return_to(return_to):
        raise HTTPException(status_code=400, detail="return_to scheme not allowed")
    try:
        state = encode_state(return_to)
        url = build_authorize_url(state)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Google calls this URL with `?code&state`. We exchange + upsert + JWT,
    then redirect back to the mobile deep link with ?jwt=... appended."""
    if error:
        # User cancelled or Google rejected — bounce them home with the error.
        return RedirectResponse(url=f"cadence://signed-in?error={urllib.parse.quote(error)}", status_code=302)
    if not (code and state):
        raise HTTPException(status_code=400, detail="missing code or state")

    try:
        decoded = decode_state(state)
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return_to = decoded.get("return_to") or ""
    if not is_allowed_return_to(return_to):
        raise HTTPException(status_code=400, detail="state.return_to invalid")

    try:
        tokens = await exchange_code_web(code)
    except PermissionError as e:
        sep = "&" if "?" in return_to else "?"
        return RedirectResponse(url=f"{return_to}{sep}error={urllib.parse.quote(str(e))}", status_code=302)

    user = await session.scalar(select(User).where(User.email == tokens.email))
    if user is None:
        user = User(email=tokens.email, name=tokens.name or "", tz="America/Toronto")
        session.add(user)
        await session.flush()
        logger.info("created user %s (%s)", user.id, user.email)
    else:
        if tokens.name and not user.name:
            user.name = tokens.name

    if tokens.refresh_token:
        user.google_refresh_token_enc = encrypt(tokens.refresh_token)
        logger.info("updated refresh token for %s", user.email)
    elif user.google_refresh_token_enc is None:
        sep = "&" if "?" in return_to else "?"
        return RedirectResponse(
            url=f"{return_to}{sep}error=no_refresh_token", status_code=302,
        )

    await session.flush()
    token_jwt = issue_jwt(user.id, user.email)
    sep = "&" if "?" in return_to else "?"
    return RedirectResponse(
        url=f"{return_to}{sep}jwt={urllib.parse.quote(token_jwt)}",
        status_code=302,
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
