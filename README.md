# Authenticator

FastAPI phone-number auth service with JWT access + refresh tokens (no OTP —
registration and login are immediate), and a simple push-notification API
for partner "services".

## ⚠️ Rotate your credentials first

The uploaded project's `.env` and `alembic.ini` contained a **live Supabase
database password in plain text** (and, before this revision, a live
Upstash Redis token that's no longer used at all). Treat the database
password as compromised since it was already exposed in a file you shared:

1. In Supabase → Project Settings → Database, reset the database password.
2. Put the **new** value only in your local `.env` (never committed) and in
   Vercel's Environment Variables dashboard.
3. If you had an Upstash database for the old OTP flow, you can delete it —
   it's no longer referenced anywhere in this project.

## What changed in this revision

- **OTP flow removed entirely.** There is no `/register` → wait for a
  Telegram code → `/confirm-otp` dance anymore, no Redis, no Telegram bot,
  no SMS. `POST /api/v1/users/register` now takes `full_name`,
  `phone_number`, `password` (and an optional `device_token`) and creates
  the account **immediately**, returning tokens right away — same as
  [Login](#-api-docs).
- **Refresh tokens added.** Register, Login, and the new
  `POST /api/v1/users/refresh` all return an `access_token` **and** a
  `refresh_token`. The server stores a SHA-256 hash of only the
  most-recently-issued refresh token per user (`users.refresh_token_hash`),
  so calling `/refresh` rotates it — the previous refresh token stops
  working the instant a new one is issued. A JWT's `"type"` claim
  (`"access"` vs `"refresh"`) keeps the two from being used for the wrong
  purpose: an access token is rejected at `/refresh`, and a refresh token is
  rejected everywhere `Authorization: Bearer` is checked.
- **`redis_client.py` deleted** and `upstash-redis` removed from
  `requirements.txt` — nothing in the project talks to Redis/Upstash
  anymore.
- **`config.py`** dropped `UPSTASH_URL`, `UPSTASH_TOKEN`, `OTP_TTL_SECONDS`,
  `BOT_USERNAME`; added `REFRESH_TOKEN_EXPIRE_DAYS` (default 60).
- **New Alembic migration** (`2f6a1d9c7b3e_add_refresh_token_hash.py`) adds
  the `refresh_token_hash` column to `users`. The old project also shipped
  **two migrations that both tried to create the same tables**
  (`1af2eabdbbdd` and `802c1aa184c0`, the second wrongly generated with
  `down_revision` pointing at the first) — `alembic upgrade head` would have
  failed the moment it hit the second one. The duplicate has been removed;
  there's now a single, linear migration history.
- **`.gitignore`** was itself ignoring `alembic.ini` (and had a stray
  `.TODO` line) — removed, so migrations work for anyone cloning the repo
  fresh.

## Still true from the previous fix-up (kept for context)

- `auth.py` / `deps.py` originally didn't run at all — missing imports and
  an `from jose import jwt` import for a package that was never installed
  (PyJWT was, but unused). Fixed to import `jwt` (PyJWT) directly.
- `main.py` never registered any router, so every `/api/v1/...` route
  404'd. Fixed.
- `database.py` and `models.py` each defined their own `DeclarativeBase`;
  `models.py` now imports the single `Base` from `database.py`.
- Hardcoded secrets in source were removed — everything comes from
  `config.py` / environment variables.
- `passlib` + `bcrypt==5.0.0` is a known-broken combination; replaced with
  the `bcrypt` library directly.
- `Notification.is_read` had no endpoint to read or set it. Added
  `GET /api/v1/notifications` and `PATCH /api/v1/notifications/{id}/read`.
- No CORS configuration; added, configurable via `CORS_ORIGINS`.

## Project layout

```
main.py                FastAPI app, CORS, router registration
config.py               Settings (env vars)
database.py             Async SQLAlchemy engine/session, shared Base
models.py               Service, User (+ refresh_token_hash), Notification
schemas.py              Pydantic request/response models
security.py             Password hashing + access/refresh JWTs
deps.py                 get_current_user (validates access tokens only)
routers/
  auth.py               register / login / refresh / me
  service.py            service registration, sending messages
  notifications.py      list / mark-read
alembic/                migrations
vercel.json
.env.example
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env         # then fill in real values
alembic upgrade head          # creates/updates the tables in your Postgres DB

uvicorn main:app --reload
```

## Deploying to Vercel

This project needs **no `vercel.json` beyond what's included** — Vercel
auto-detects a FastAPI `app` exported from `main.py` at the project root.

1. Push this project to a GitHub/GitLab/Bitbucket repo (`.env` stays out,
   `.gitignore` already handles that).
2. Import the repo at vercel.com/new, or run `vercel` from this directory.
3. In the Vercel project's **Settings → Environment Variables**, add:
   `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_DAYS`,
   `REFRESH_TOKEN_EXPIRE_DAYS`, `CORS_ORIGINS`, `DEBUG` — using your
   **rotated** database credentials, not the old ones.
4. **Run `alembic upgrade head` yourself, from your own machine, before or
   right after the first deploy.** Vercel's build step doesn't run it
   automatically, and a serverless function is the wrong place to run
   migrations against a live database.
5. Deploy. `GET /health` should return `{"status": "ok"}`.

Database access already goes through Supabase's pgbouncer transaction pooler
(port 6543) with `NullPool` on the app side, which is the recommended setup
for short-lived serverless connections — no extra config needed for that.

## API docs

Full endpoint-by-endpoint reference (bodies, responses, error codes) is in
[`API.md`](./API.md). Interactive Swagger UI is also always available at
`/docs` once the app is running.
