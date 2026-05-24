-- Cadence-api schema. Loaded by db.init.bootstrap() on first start.
-- Idempotent: every CREATE uses IF NOT EXISTS. Safe to re-run.
--
-- Design notes:
--   * tasks is source-polymorphic via (source_type, source_ref). v2 news adds
--     rows without a migration. Manual tasks: source_type='manual', source_ref=null.
--   * Google refresh tokens are encrypted at rest in users.google_refresh_token_enc
--     (Fernet) — never returned to the client.
--   * gmail_history_id is the watermark for delta polls (users.messages.list?historyId=).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email                     TEXT         NOT NULL UNIQUE,
    name                      TEXT         NOT NULL DEFAULT '',
    tz                        TEXT         NOT NULL DEFAULT 'America/Toronto',
    google_refresh_token_enc  BYTEA,                              -- Fernet-encrypted; nullable until OAuth completes
    gmail_history_id          TEXT,                               -- Gmail API delta watermark
    last_polled_at            TIMESTAMPTZ,
    digest_hour_local         SMALLINT     NOT NULL DEFAULT 7,    -- 0-23, hour in user's tz
    created_at                TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── Devices (APNs / FCM tokens) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS devices (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform     TEXT         NOT NULL CHECK (platform IN ('ios', 'android')),
    push_token   TEXT         NOT NULL,
    last_seen_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, push_token)
);
CREATE INDEX IF NOT EXISTS ix_devices_user ON devices(user_id);

-- ── Emails ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS emails (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gmail_msg_id    TEXT         NOT NULL,
    gmail_thread_id TEXT,
    from_addr       TEXT         NOT NULL DEFAULT '',
    subject         TEXT         NOT NULL DEFAULT '',
    snippet         TEXT         NOT NULL DEFAULT '',
    body_text       TEXT         NOT NULL DEFAULT '',
    received_at     TIMESTAMPTZ  NOT NULL,
    summary         TEXT,
    is_urgent       BOOLEAN      NOT NULL DEFAULT FALSE,
    category        TEXT,
    summary_model   TEXT,
    processed_at    TIMESTAMPTZ,                                  -- when LLM summary completed
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, gmail_msg_id)
);
CREATE INDEX IF NOT EXISTS ix_emails_user_received  ON emails(user_id, received_at DESC);
CREATE INDEX IF NOT EXISTS ix_emails_unprocessed    ON emails(user_id) WHERE processed_at IS NULL;

-- ── Tasks (source-polymorphic) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type   TEXT         NOT NULL CHECK (source_type IN ('email', 'news', 'manual')),
    source_ref    UUID,                                          -- emails.id / news_items.id; null for manual
    title         TEXT         NOT NULL,
    notes         TEXT         NOT NULL DEFAULT '',
    due_date      DATE,
    due_time      TIME,
    remind_at     TIMESTAMPTZ,                                   -- when APNs should fire for this task
    priority      TEXT         NOT NULL DEFAULT 'low' CHECK (priority IN ('low', 'med', 'high')),
    status        TEXT         NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'snoozed', 'deleted')),
    confidence    REAL,                                          -- only set for LLM-extracted tasks
    rationale     TEXT,                                          -- only set for LLM-extracted tasks
    extracted_model TEXT,
    completed_at  TIMESTAMPTZ,
    reminded_at   TIMESTAMPTZ,                                   -- last APNs delivery for this task
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_tasks_user_status_due ON tasks(user_id, status, due_date);
CREATE INDEX IF NOT EXISTS ix_tasks_user_remind    ON tasks(user_id, remind_at) WHERE status = 'open' AND remind_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_tasks_source        ON tasks(source_type, source_ref);

-- ── Digests ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS digests (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    digest_date   DATE         NOT NULL,                          -- date in user's tz
    body_md       TEXT         NOT NULL,
    highlights    JSONB        NOT NULL DEFAULT '[]'::jsonb,
    generated_model TEXT,
    generated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    delivered_at  TIMESTAMPTZ,                                    -- when APNs went out
    UNIQUE (user_id, digest_date)
);
CREATE INDEX IF NOT EXISTS ix_digests_user_date ON digests(user_id, digest_date DESC);

-- ── v2 reservations (no rows yet — schema reserved for news pipeline) ───────
CREATE TABLE IF NOT EXISTS news_sources (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        TEXT         NOT NULL,                            -- 'rss', 'topic', etc.
    config      JSONB        NOT NULL DEFAULT '{}'::jsonb,
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news_items (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_id     UUID         NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
    external_id   TEXT         NOT NULL,
    title         TEXT         NOT NULL DEFAULT '',
    url           TEXT         NOT NULL DEFAULT '',
    body_text     TEXT         NOT NULL DEFAULT '',
    published_at  TIMESTAMPTZ,
    summary       TEXT,
    summary_model TEXT,
    processed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, source_id, external_id)
);
