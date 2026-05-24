# Cadence — mobile (iOS-first, Expo prebuild)

## First-time setup

```bash
# 1. Install deps (creates node_modules + lock file)
cd p:\Avyra\avyra-cadence\mobile
npm install

# 2. Copy env and fill in Google OAuth client ids + cadence-api URL
copy .env.example .env
# edit .env

# 3. Generate the native ios/ folder (committed afterwards)
npx expo prebuild --platform ios --clean

# 4. Place app icon + splash images
#    - assets/icon.png    (1024×1024)
#    - assets/splash.png  (1242×2436 or similar)

# 5. Run on iOS Simulator (requires Xcode)
npx expo run:ios
```

## What you need from Google Cloud Console

1. Create an OAuth consent screen — add scope `https://www.googleapis.com/auth/gmail.readonly`.
2. Create **two** OAuth client IDs:
   - **iOS app** (bundle id `com.avyra.cadence`) — for the device-side PKCE flow.
   - **Web application** — its client id + secret go into `cadence-api`'s `.env`. We set the id_token `aud` to this so cadence-api can verify against it.
3. Set `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` to the iOS client id and `EXPO_PUBLIC_GOOGLE_CLIENT_ID` to the web client id.

## What runs where

| Piece | Where |
|---|---|
| Mobile UI | this folder (Expo / React Native) |
| Backend API | `../services/cadence-api/` (FastAPI :8010 + Postgres :5433) |
| LLM gateway | existing `avyra-voice-assistant/services/ai-engine` (:8000) — unchanged for voice, gained a `/api/cadence/*` route |
| Local LLM | existing Ollama (:11434) |

## Running the full stack locally

```bash
# Terminal 1 — backend (DB + cadence-api)
cd p:\Avyra\avyra-cadence
copy .env.example .env             # fill in
docker compose up -d --build

# Terminal 2 — ai-engine (already running in your voice stack; nothing to change)
#   make sure AI_ENGINE_SHARED_SECRET is set on that container to the same value
#   you put in cadence-api's .env

# Terminal 3 — mobile
cd mobile
npx expo run:ios
```

## File layout

```
app/                          ← expo-router file-based routes
  _layout.tsx                 ← root: providers + AuthGate
  index.tsx                   ← redirect stub
  (auth)/sign-in.tsx          ← Google sign-in
  (tabs)/_layout.tsx          ← bottom tabs
  (tabs)/tasks.tsx            ← Tasks (LLM + manual unified)
  (tabs)/inbox.tsx            ← Inbox (per-email summaries)
  (tabs)/digest.tsx           ← Daily digest (markdown)
  (tabs)/settings.tsx         ← Account, schedule info, sign out
  email/[id].tsx              ← Email detail + extracted tasks
  task/new.tsx                ← Manual task sheet
src/
  config.ts                   ← EXPO_PUBLIC_* env vars
  theme.ts                    ← palette + spacing
  api/{client,types,hooks}.ts ← HTTP + React Query
  auth/{google,session}.ts    ← OAuth + Zustand session
  push/register.ts            ← APNs token registration
  components/{TaskRow,EmailRow}.tsx
```
