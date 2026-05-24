# Cadence — subproject index

Personal inbox + task agent. iOS-first React Native app (Expo prebuild) connects to user's Gmail, calls the existing `ai-engine` (port 8000) for LLM summarization + task extraction, surfaces everything in a unified in-app task list with push notifications. Manual tasks are first-class. v2: news summarization (same source-polymorphic schema).

## Stack

- **Mobile (`mobile/`)** — React Native via Expo prebuild, TypeScript, React Navigation, Zustand, TanStack Query, NativeWind.
- **Backend (`services/cadence-api/`)** — FastAPI on **port 8010**, SQLAlchemy + Postgres, APScheduler, APNs for push, Gmail API (Pub/Sub push → poll fallback).
- **LLM** — Calls `ai-engine` (:8000) `/api/cadence/{summarize,extract_tasks,digest}`. ai-engine routes to local Ollama (:11434). Never call Ollama directly from `cadence-api` — preserves single-AI-architecture rule.

## Entry points

- `services/cadence-api/main.py` — FastAPI app, mounts routes, starts scheduler
- `services/cadence-api/db/schema.sql` — Postgres tables (users, devices, emails, tasks, digests; news_sources/items reserved for v2)
- `services/cadence-api/routes/` — `auth.py`, `emails.py`, `tasks.py`, `devices.py`
- `services/cadence-api/llm/ai_engine_client.py` — HTTP client to ai-engine `/api/cadence/*`
- `services/cadence-api/scheduler.py` — daily digest, overdue sweep, Gmail poll fallback
- `mobile/src/` — RN code (api/, auth/, screens/, components/, store/, push/)

## Key interfaces

- **Mobile ↔ cadence-api:** bearer JWT after `/auth/google/exchange`. Endpoints: `/me`, `/emails`, `/tasks` (incl. POST for manual tasks), `/digest/today`, `/devices`, `/refresh`.
- **cadence-api ↔ ai-engine:** shared bearer token (`AI_ENGINE_SHARED_SECRET`). Request carries `source_type: "email" | "news" | "manual"` so the same route serves future sources.
- **Tasks schema is source-polymorphic** — `source_type` ∈ `{email, news, manual}`, `source_ref` nullable. News (v2) adds rows, no migration.

## Gotchas

- `gmail.readonly` scope requires Google security assessment before public release (4–6 weeks). Beta cap is 100 users on unverified app.
- Google refresh tokens encrypted at rest (Fernet, key from env). Never return to client.
- APNs: dev uses Expo's relay; **prod must use own APNs cert** — emails should not flow through Expo's relay.
- iOS BackgroundTasks unreliable for refresh timing; primary refresh = server-side poller + APNs.
- ai-engine domain is named **`cadence`**, not `inbox` — chosen so v2 news fits under the same domain.

## Ignore globs

`**/node_modules/**`, `**/.venv/**`, `mobile/ios/Pods/**`, `mobile/ios/build/**`, `mobile/android/build/**`, `mobile/android/.gradle/**`, `mobile/.expo/**`.

## Plan / changelog

- Full plan: `C:\Users\patel\.claude\plans\okay-you-are-working-agile-eich.md`
- See `CHANGELOG.md` for incremental progress.
