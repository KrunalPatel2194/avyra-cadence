"""HTTP client for ai-engine's `/api/cadence/*` endpoints.

cadence-api never calls Ollama directly — it always goes through ai-engine.
This preserves the single-AI-architecture rule (only ai-engine talks to the LLM)
and centralizes prompt management in the voice-assistant config.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("cadence.llm.client")


class AiEngineError(RuntimeError):
    """Raised when ai-engine returns a non-2xx or invalid response."""


class AiEngineClient:
    def __init__(self, base_url: str | None = None, secret: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.AI_ENGINE_URL).rstrip("/")
        self.secret = secret or settings.AI_ENGINE_SHARED_SECRET
        self.timeout = timeout if timeout is not None else float(settings.AI_ENGINE_TIMEOUT_SECONDS)
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            if not self.secret:
                raise AiEngineError("AI_ENGINE_SHARED_SECRET not set")
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.secret}"},
                timeout=httpx.Timeout(self.timeout, connect=10.0),
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        http = await self._client()
        try:
            resp = await http.post(path, json=payload)
        except httpx.HTTPError as e:
            raise AiEngineError(f"ai-engine transport error on {path}: {e}") from e
        if resp.status_code >= 400:
            snippet = resp.text[:300].replace("\n", " ")
            raise AiEngineError(f"ai-engine {resp.status_code} on {path}: {snippet}")
        try:
            return resp.json()
        except ValueError as e:
            raise AiEngineError(f"ai-engine returned non-JSON on {path}: {resp.text[:200]}") from e

    # ── Public methods ─────────────────────────────────────────────────────
    async def summarize(
        self,
        *,
        source_type: str,
        from_addr: str,
        subject: str,
        received_at: datetime | str,
        body: str,
        source_id: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "source_type": source_type,
            "source_id": source_id,
            "from": from_addr,
            "subject": subject,
            "received_at": _iso(received_at),
            "body": body,
        }
        if model:
            payload["model"] = model
        return await self._post("/api/cadence/summarize", payload)

    async def extract_tasks(
        self,
        *,
        source_type: str,
        from_addr: str,
        subject: str,
        received_at: datetime | str,
        user_tz: str,
        body: str,
        source_id: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "source_type": source_type,
            "source_id": source_id,
            "from": from_addr,
            "subject": subject,
            "received_at": _iso(received_at),
            "user_tz": user_tz,
            "body": body,
        }
        if model:
            payload["model"] = model
        return await self._post("/api/cadence/extract_tasks", payload)

    async def digest(
        self,
        *,
        user_name: str,
        user_tz: str,
        today: str,
        summaries: list[dict],
        open_tasks: list[dict],
        overdue_tasks: list[dict],
        model: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user_name": user_name,
            "user_tz": user_tz,
            "today": today,
            "summaries": summaries,
            "open_tasks": open_tasks,
            "overdue_tasks": overdue_tasks,
        }
        if model:
            payload["model"] = model
        return await self._post("/api/cadence/digest", payload)

    async def health(self) -> dict[str, Any]:
        """Unauthenticated probe — confirms ai-engine has the cadence domain loaded."""
        http = await self._client()
        resp = await http.get("/api/cadence/health")
        resp.raise_for_status()
        return resp.json()


def _iso(v: datetime | str) -> str:
    if isinstance(v, datetime):
        return v.isoformat()
    return v


# Process-wide singleton — fine because ai-engine is stateless and httpx is async-safe.
_client_singleton: AiEngineClient | None = None


def get_client() -> AiEngineClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = AiEngineClient()
    return _client_singleton
