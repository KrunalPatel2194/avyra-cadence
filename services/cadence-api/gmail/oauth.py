"""Google OAuth — exchange an auth code for refresh/access tokens, validate id_token.

Mobile-side flow (Expo / RN):
    1. expo-auth-session runs Google OAuth with PKCE in the iOS browser
    2. Receives { code, codeVerifier } back from the redirect
    3. POSTs both to cadence-api `/auth/google/exchange` along with redirect_uri
    4. We exchange the code with Google's token endpoint, validate id_token,
       and return our own JWT.

We require offline access (`access_type=offline`) and `prompt=consent` on the
mobile side so Google actually returns a refresh_token — without those,
subsequent sign-ins return only an access_token and we lose the ability to
re-fetch Gmail in the background.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from config import settings

logger = logging.getLogger("cadence.gmail.oauth")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
# Google appends openid/profile/email automatically when id_token is requested,
# but we list them so the consent screen check is unambiguous.
REQUIRED_SCOPES = {
    GMAIL_SCOPE,
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
}


@dataclass
class GoogleTokens:
    access_token: str
    refresh_token: str       # may be empty on subsequent sign-ins; we handle that case in the route
    id_token: str
    expires_in: int
    scope: str
    email: str
    google_sub: str          # stable Google user id
    name: str


async def exchange_code(code: str, code_verifier: str, redirect_uri: str) -> GoogleTokens:
    """Trade a PKCE auth code for tokens. Validates the id_token signature.

    For an iOS OAuth client, Google does NOT require a client_secret — the
    code_verifier proves possession. For a Web OAuth client, a secret IS
    required. We send the secret only if one is configured.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise RuntimeError("GOOGLE_CLIENT_ID not configured")

    payload = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if settings.GOOGLE_CLIENT_SECRET:
        payload["client_secret"] = settings.GOOGLE_CLIENT_SECRET

    # Diagnostic — log what we send (without leaking code/verifier full text).
    logger.info(
        "exchange request: redirect_uri=%r client_id_tail=...%s code_len=%d verifier_len=%d secret_set=%s",
        redirect_uri,
        settings.GOOGLE_CLIENT_ID[-14:] if settings.GOOGLE_CLIENT_ID else "",
        len(code or ""),
        len(code_verifier or ""),
        bool(settings.GOOGLE_CLIENT_SECRET),
    )

    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(GOOGLE_TOKEN_URL, data=payload)
    if resp.status_code != 200:
        logger.error("Google token exchange failed: %s — payload: %s — response: %s",
                     resp.status_code, {k: v[:20] if isinstance(v, str) else v for k, v in payload.items()}, resp.text[:500])
        raise PermissionError(f"google token exchange failed ({resp.status_code})")
    body = resp.json()

    access_token = body.get("access_token") or ""
    refresh_token = body.get("refresh_token") or ""    # may be empty on re-auth
    id_token_str = body.get("id_token") or ""
    scope = body.get("scope") or ""
    expires_in = int(body.get("expires_in") or 0)

    if not (access_token and id_token_str):
        raise PermissionError("google response missing access_token / id_token")

    # Validate id_token. google-auth verifies the JWT signature against
    # Google's published keys (cached) and checks aud / iss / exp.
    try:
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            audience=settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise PermissionError(f"google id_token verification failed: {e}") from e

    # Hard requirement: Gmail scope must be present.
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
