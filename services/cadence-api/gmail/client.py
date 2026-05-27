"""Gmail API client — fetch new messages for a user.

google-api-python-client is synchronous. All Gmail calls in this module are
sync; the watcher wraps them with `asyncio.to_thread` so they don't block the
event loop.

We never use Gmail's history.list — it has 7-day retention and a 2h poll
cadence (plus the missed-day window after a long pause) makes it brittle.
Instead we use `q=after:<unix>` which is straightforward and bounded by the
user's last poll watermark.
"""
from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings
from gmail.oauth import GMAIL_SCOPE

logger = logging.getLogger("cadence.gmail.client")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
# Hard cap on message body size we'll ship to the LLM (12k chars matches the
# ai-engine route's truncation budget). Avoids feeding it 200kb mailing-list
# digests.
MAX_BODY_CHARS = 12_000
# How many messages to pull per poll. With a 2h cadence and a typical inbox,
# 50 is plenty; cap protects against pathological catch-up runs.
MAX_MESSAGES_PER_POLL = 50


@dataclass
class GmailMessage:
    msg_id: str
    thread_id: str
    from_addr: str
    from_name: str
    subject: str
    snippet: str
    body_text: str
    received_at: datetime
    label_ids: list[str]

    @property
    def is_promo(self) -> bool:
        # Gmail categorizes promos; we use this to skip summarization for
        # marketing mail rather than burn LLM cycles.
        return "CATEGORY_PROMOTIONS" in self.label_ids or "CATEGORY_FORUMS" in self.label_ids


def _build_creds(refresh_token: str) -> Credentials:
    # The refresh_token was issued by Google for the Web client (the native
    # iOS Sign-In SDK requests offline access under the webClientId). To
    # refresh it we MUST use the Web client's id + secret — the iOS client
    # id won't work because Google scopes refresh tokens to the issuing
    # client_id.
    client_id = settings.GOOGLE_WEB_CLIENT_ID or settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_WEB_CLIENT_SECRET or settings.GOOGLE_CLIENT_SECRET or None
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[GMAIL_SCOPE],
    )


def _service(refresh_token: str):
    creds = _build_creds(refresh_token)
    # Force a refresh up front so a stale token surfaces here, not deep in a paged loop.
    creds.refresh(GoogleRequest())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _decode_part(data: str | None) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _walk_payload(payload: dict[str, Any]) -> tuple[str, str]:
    """Return (text_plain, text_html) from a Gmail payload tree (first non-empty wins)."""
    text_plain: str = ""
    text_html: str = ""

    def walk(p: dict[str, Any]) -> None:
        nonlocal text_plain, text_html
        mime = p.get("mimeType", "")
        body = (p.get("body") or {}).get("data")
        if mime == "text/plain" and not text_plain:
            text_plain = _decode_part(body)
        elif mime == "text/html" and not text_html:
            text_html = _decode_part(body)
        for child in p.get("parts") or []:
            walk(child)

    walk(payload)
    return text_plain, text_html


_WHITESPACE_RE = re.compile(r"[ \t]+")
_NEWLINES_RE = re.compile(r"\n{3,}")
_QUOTED_RE = re.compile(r"^\s*>.*$", re.MULTILINE)


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head", "meta", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _clean_body(text: str) -> str:
    # Drop quoted reply blocks (lines starting with "> ").
    text = _QUOTED_RE.sub("", text)
    # Collapse whitespace.
    text = _WHITESPACE_RE.sub(" ", text)
    text = _NEWLINES_RE.sub("\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = text.strip()
    if len(text) > MAX_BODY_CHARS:
        text = text[:MAX_BODY_CHARS] + "\n…[truncated]"
    return text


def _parse_message(raw: dict[str, Any]) -> GmailMessage:
    headers = {h["name"].lower(): h["value"] for h in (raw.get("payload", {}).get("headers") or [])}
    from_raw = headers.get("from", "")
    from_name, from_addr = parseaddr(from_raw)
    subject = headers.get("subject", "")

    date_hdr = headers.get("date", "")
    try:
        received_at = parsedate_to_datetime(date_hdr) if date_hdr else None
    except (TypeError, ValueError):
        received_at = None
    if received_at is None:
        # Gmail provides `internalDate` (ms epoch) as a reliable fallback.
        ms = int(raw.get("internalDate") or 0)
        received_at = datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else datetime.now(timezone.utc)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)

    text_plain, text_html = _walk_payload(raw.get("payload", {}))
    body = text_plain or _html_to_text(text_html)
    body = _clean_body(body)

    return GmailMessage(
        msg_id=raw["id"],
        thread_id=raw.get("threadId", ""),
        from_addr=(from_addr or "").lower(),
        from_name=from_name or "",
        subject=subject,
        snippet=raw.get("snippet", "")[:500],
        body_text=body,
        received_at=received_at,
        label_ids=list(raw.get("labelIds") or []),
    )


def _list_message_ids(svc, query: str, max_results: int) -> list[str]:
    ids: list[str] = []
    page_token: str | None = None
    remaining = max_results
    while remaining > 0:
        kwargs = {"userId": "me", "q": query, "maxResults": min(remaining, 100)}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = svc.users().messages().list(**kwargs).execute()
        batch = [m["id"] for m in (resp.get("messages") or [])]
        ids.extend(batch)
        remaining -= len(batch)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids[:max_results]


def fetch_new_messages_sync(
    refresh_token: str,
    *,
    since: datetime | None,
    limit: int = MAX_MESSAGES_PER_POLL,
) -> list[GmailMessage]:
    """Fetch messages from the last `GMAIL_LOOKBACK_DAYS` days, regardless
    of `since`. The 5-day window is intentional — it catches anything we
    missed while offline, and the watcher dedupes via the unique
    (user_id, gmail_msg_id) index so already-processed mail isn't
    re-summarized. `since` is ignored on purpose; kept in the signature for
    callers that haven't been updated yet.

    Skips Gmail chats. Returns oldest-first so callers can stamp
    `last_polled_at` from the newest after a successful run.
    """
    svc = _service(refresh_token)
    lookback = max(1, settings.GMAIL_LOOKBACK_DAYS)
    since = datetime.now(timezone.utc) - timedelta(days=lookback)
    after_epoch = int(since.timestamp())
    # `-in:chats` excludes Hangouts; `-from:me` skips sent mail.
    query = f"after:{after_epoch} -in:chats -from:me"

    try:
        msg_ids = _list_message_ids(svc, query, max_results=limit)
    except HttpError as e:
        logger.error("gmail list failed: %s", e)
        raise

    out: list[GmailMessage] = []
    for mid in msg_ids:
        try:
            raw = svc.users().messages().get(userId="me", id=mid, format="full").execute()
        except HttpError as e:
            logger.warning("gmail get failed for %s: %s", mid, e)
            continue
        try:
            out.append(_parse_message(raw))
        except Exception as e:
            logger.warning("gmail parse failed for %s: %s", mid, e)

    out.sort(key=lambda m: m.received_at)
    return out
