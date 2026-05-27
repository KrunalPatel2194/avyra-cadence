"""Cadence-api settings — loaded from env vars (or a .env at project root)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Service ────────────────────────────────────────────────────────────
    SERVICE_NAME: str = "cadence-api"
    PORT: int = 8010
    LOG_LEVEL: str = "INFO"

    # ── Postgres (asyncpg DSN) ─────────────────────────────────────────────
    # Example: postgresql+asyncpg://cadence:cadence@localhost:5433/cadence
    POSTGRES_DSN: str = "postgresql+asyncpg://cadence:cadence@localhost:5433/cadence"

    # ── Crypto ─────────────────────────────────────────────────────────────
    # Fernet key for encrypting Google refresh tokens at rest.
    # Generate once: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FERNET_KEY: str = ""
    # JWT signing secret (HS256) for mobile-facing bearer tokens.
    JWT_SECRET: str = ""
    JWT_TTL_DAYS: int = 30

    # ── Google OAuth ───────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # RN/Expo redirect URI registered in the Google Cloud OAuth client.
    GOOGLE_REDIRECT_URI: str = ""

    # ── Server-mediated OAuth (Web client, used by mobile in Expo Go) ──────
    # Required for the /auth/google/start + /auth/google/callback flow.
    # Create a "Web application" OAuth client in Google Console with
    # `<PUBLIC_API_URL>/auth/google/callback` registered as an Authorized
    # redirect URI.
    GOOGLE_WEB_CLIENT_ID: str = ""
    GOOGLE_WEB_CLIENT_SECRET: str = ""
    # Where THIS service is reachable from the public internet — the value
    # used to build the redirect_uri sent to Google. Must EXACTLY equal what
    # you register in Google Console.
    PUBLIC_API_URL: str = ""

    # ── ai-engine ──────────────────────────────────────────────────────────
    AI_ENGINE_URL: str = "http://localhost:8000"
    # Must match the same env var on the ai-engine container — bearer token
    # exchanged between cadence-api ↔ ai-engine.
    AI_ENGINE_SHARED_SECRET: str = ""
    AI_ENGINE_TIMEOUT_SECONDS: int = 180

    # ── Scheduler cadence ──────────────────────────────────────────────────
    # User-set policy: poll Gmail every 4 hours, scanning the last 5 days
    # every time. No manual refresh path exposed in the app — scheduler is
    # the only ingestion trigger (plus an auto-poll right after sign-in).
    GMAIL_POLL_INTERVAL_SECONDS: int = 14400         # 4h
    GMAIL_LOOKBACK_DAYS: int = 5
    OVERDUE_SWEEP_INTERVAL_SECONDS: int = 3600       # 1h
    DIGEST_LOCAL_HOUR: int = 7                       # 07:00 in each user's tz

    # ── Dev backdoor ───────────────────────────────────────────────────────
    # When true, exposes POST /auth/dev-login which issues a real JWT for any
    # email without going through Google. ONLY for local development — Expo
    # Go can't use the real iOS OAuth client, so this lets you boot the app
    # and exercise the rest of the surface area. Set to false (or unset) for
    # any non-dev environment.
    DEV_LOGIN_ENABLED: bool = False

    # ── APNs (push) ────────────────────────────────────────────────────────
    APNS_USE_SANDBOX: bool = True
    APNS_TEAM_ID: str = ""
    APNS_KEY_ID: str = ""
    # Either path to the .p8 file mounted into the container, or the literal
    # PEM contents in APNS_KEY_PEM (handy for env-only secret stores).
    APNS_KEY_PATH: str = ""
    APNS_KEY_PEM: str = ""
    APNS_TOPIC: str = ""                             # bundle id, e.g. com.avyra.cadence


settings = Settings()
