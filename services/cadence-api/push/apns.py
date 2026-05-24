"""APNs push sender — token-based auth via aioapns.

Single in-process client (aioapns manages the HTTP/2 connection pool). The
sender is best-effort: failures are logged, never raised. Notifications are
not critical to user state — Postgres is the source of truth.

In dev (no APNs creds), the sender is a no-op and just logs intent.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import Device

logger = logging.getLogger("cadence.push.apns")

_client = None
_lock = asyncio.Lock()


def _creds_present() -> bool:
    return bool(settings.APNS_TEAM_ID and settings.APNS_KEY_ID and settings.APNS_TOPIC and (
        settings.APNS_KEY_PATH or settings.APNS_KEY_PEM
    ))


async def _get_client():
    global _client
    if _client is not None:
        return _client
    if not _creds_present():
        return None
    async with _lock:
        if _client is not None:
            return _client
        try:
            from aioapns import APNs                                       # type: ignore[import-not-found]
        except ImportError:
            logger.error("aioapns not installed — push disabled")
            return None
        try:
            key_arg: dict[str, Any] = {}
            if settings.APNS_KEY_PATH:
                key_arg["key"] = settings.APNS_KEY_PATH
            else:
                # aioapns accepts the PEM body via a temporary file approach;
                # write once at startup, never logged.
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix=".p8", delete=False)
                tmp.write(settings.APNS_KEY_PEM.encode("utf-8"))
                tmp.close()
                key_arg["key"] = tmp.name
            _client = APNs(
                key_id=settings.APNS_KEY_ID,
                team_id=settings.APNS_TEAM_ID,
                topic=settings.APNS_TOPIC,
                use_sandbox=settings.APNS_USE_SANDBOX,
                **key_arg,
            )
            logger.info("apns client initialised (sandbox=%s)", settings.APNS_USE_SANDBOX)
        except Exception as e:
            logger.error("apns init failed: %s", e)
            _client = None
    return _client


async def send_to_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    title: str,
    body: str,
    category: str = "general",
    payload: dict[str, Any] | None = None,
    badge: int | None = None,
) -> int:
    """Deliver a push to every device registered for `user_id`. Returns count sent."""
    devices = (await session.scalars(select(Device).where(Device.user_id == user_id))).all()
    if not devices:
        return 0

    client = await _get_client()
    if client is None:
        logger.info("apns no-op (no creds) user=%s title=%r body=%r", user_id, title, body[:80])
        return 0

    try:
        from aioapns import NotificationRequest, PushType                  # type: ignore[import-not-found]
    except ImportError:
        return 0

    sent = 0
    for d in devices:
        if d.platform != "ios":
            # Android / FCM is wired separately when we get there.
            continue
        aps_payload: dict[str, Any] = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "category": category,
            },
            "data": payload or {},
        }
        if badge is not None:
            aps_payload["aps"]["badge"] = badge
        req = NotificationRequest(
            device_token=d.push_token,
            message=aps_payload,
            push_type=PushType.ALERT,
        )
        try:
            resp = await client.send_notification(req)
            if resp.is_successful:
                sent += 1
            else:
                logger.warning(
                    "apns failed user=%s token=%s status=%s reason=%s",
                    user_id, d.push_token[:12], resp.status, resp.description,
                )
        except Exception as e:
            logger.warning("apns send raised user=%s: %s", user_id, e)
    return sent
