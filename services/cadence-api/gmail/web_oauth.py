"""Server-mediated Google OAuth — used by the mobile client in environments
where the native iOS OAuth flow isn't available (Expo Go, web app later, etc).

Flow:
    Mobile  --open WebBrowser-->  GET /auth/google/start?return_to=<deep_link>
    Backend --redirect-->          accounts.google.com/.../authorize?... (Web client)
    User auth + consent
    Google  --redirect-->          GET /auth/google/callback?code&state
    Backend exchanges code → upserts user → issues JWT → redirects to:
                                   <return_to>?jwt=<jwt>
    Mobile WebBrowser closes with that URL; mobile parses ?jwt and signs in.

Security properties:
    - `state` carries a nonce + return_to, signed via JWT so the callback
      can verify integrity without server-side storage.
    - Only `return_to` values matching the configured allowlist of schemes
      are accepted, preventing open-redirect.
    - The refresh_token never leaves the backend.
"""
from __future__ import annotations

import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt as jose_jwt

from config import settings
from gmail.oauth import GMAIL_SCOPE, GOOGLE_TOKEN_URL, GoogleTokens

logger = logging.getLogger("cadence.gmail.web_oauth")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

# return_to URLs must start with one of these (deep links from the mobile app).
ALLOWED_RETURN_SCHEMES = (
    "cadence://",          # native dev client deep link
    "exp://",              # Expo Go deep link (dev)
    "exps://",             # Expo Go over HTTPS
    "http://localhost",    # web in dev
    "https://localhost",
)

STATE_TTL_MINUTES = 10


def is_allowed_return_to(url: str) -> bool:
    return any(url.startswith(prefix) for prefix in ALLOWED_RETURN_SCHEMES)


def encode_state(return_to: str) -> str:
    payload = {
        "nonce": secrets.token_urlsafe(16),
        "return_to": return_to,
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)).timestamp()),
    }
    return jose_jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_state(state: str) -> dict:
    try:
        return jose_jwt.decode(state, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError as e:
        raise PermissionError(f"invalid state: {e}") from e


def callback_url() -> str:
    """The redirect URI sent to Google. MUST equal what's registered in the
    Google Console for the Web client."""
    base = settings.PUBLIC_API_URL.rstrip("/")
    if not base:
        raise RuntimeError("PUBLIC_API_URL not configured")
    return f"{base}/auth/google/callback"


def build_authorize_url(state: str) -> str:
    if not settings.GOOGLE_WEB_CLIENT_ID:
        raise RuntimeError("GOOGLE_WEB_CLIENT_ID not configured")
    params = {
        "client_id": settings.GOOGLE_WEB_CLIENT_ID,
        "redirect_uri": callback_url(),
        "response_type": "code",
        "scope": "openid email profile " + GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",            # force refresh_token issuance
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_web(code: str, *, redirect_uri: str | None = None) -> GoogleTokens:
    """Exchange a Web-flow auth code. Web clients DO use client_secret.

    For codes issued via the native iOS Sign-In SDK (`serverAuthCode`), pass
    `redirect_uri=""` — Google expects an empty string in that case because
    no redirect actually happened. For codes issued via the WebBrowser
    redirect flow, omit it to default to the registered callback URL.
    """
    if not (settings.GOOGLE_WEB_CLIENT_ID and settings.GOOGLE_WEB_CLIENT_SECRET):
        raise RuntimeError("GOOGLE_WEB_CLIENT_ID / SECRET not configured")

    payload = {
        "code": code,
        "client_id": settings.GOOGLE_WEB_CLIENT_ID,
        "client_secret": settings.GOOGLE_WEB_CLIENT_SECRET,
        "redirect_uri": callback_url() if redirect_uri is None else redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(GOOGLE_TOKEN_URL, data=payload)
    if resp.status_code != 200:
        logger.error("web token exchange failed: %s — %s", resp.status_code, resp.text[:500])
        raise PermissionError(f"google token exchange failed ({resp.status_code})")
    body = resp.json()

    access_token = body.get("access_token") or ""
    refresh_token = body.get("refresh_token") or ""
    id_token_str = body.get("id_token") or ""
    scope = body.get("scope") or ""
    expires_in = int(body.get("expires_in") or 0)

    if not (access_token and id_token_str):
        raise PermissionError("google response missing access_token / id_token")

    try:
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            audience=settings.GOOGLE_WEB_CLIENT_ID,
        )
    except ValueError as e:
        raise PermissionError(f"google id_token verification failed: {e}") from e

    granted = set(scope.split())
    if GMAIL_SCOPE not in granted:
        raise PermissionError(f"gmail scope not granted; got {granted!r}")

    return GoogleTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=id_token_str,
        expires_in=expires_in,
        scope=scope,
        email=(idinfo.get("email") or "").lower(),
        google_sub=idinfo.get("sub") or "",
        name=idinfo.get("name") or "",
    )
