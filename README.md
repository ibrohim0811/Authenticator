# Authenticator

FastAPI phone-number auth service with Telegram-bot-delivered OTP, JWT sessions,
and a simple push-notification API for partner "services".

## ⚠️ Rotate your credentials first

The uploaded project's `.env` and `alembic.ini` contained a **live Supabase
database password and an Upstash Redis token in plain text**. Those values are
not reused anywhere in this rebuilt project, but since they were already
exposed in a file you shared, treat them as compromised:

1. In Supabase → Project Settings → Database, reset the database password.
2. In Upstash → your database → reset/regenerate the REST token.
3. Put the **new** values only in your local `.env` (never committed) and in
   Vercel's Environment Variables dashboard.

## What was actually broken

- **`auth.py` / `deps.py` didn't run at all.** They used `User`, `get_db`,
  `select`, `jwt`, `JWTError`, `status`, `uuid` without importing any of
  them, and imported `from jose import jwt` — a package that was never in
  `requirements.txt` (PyJWT was, but unused).
- **`main.py` never registered any router.** `/api/v1/users/...`,
  `/api/v1/services/...`, `/api/v1/messages/...` all 404'd — only `/` worked.
- **Two different, conflicting `Base` classes.** `database.py` and
  `models.py` each defined their own `DeclarativeBase`, and models were
  attached to the one in `models.py` while Alembic pointed at the one in
  `database.py`. That's why the existing migration's `upgrade()`/`downgrade()`
  were empty — autogenerate never saw your tables. Fixed by having `models.py`
  import the single `Base` from `database.py`.
- **`routers/user.py` referenced `OTPCode`, a model that doesn't exist**
  anywhere in `models.py`, and separately created incomplete `User` rows
  (phone number only, no password) before OTP verification, which would have
  collided with the real registration flow in `auth.py`. Rewritten so all OTP
  state lives in Redis (matching the pattern `auth.py` already used) and no
  user row is created until the code is confirmed.
- **Hardcoded secrets in source**: a fallback `SECRET_KEY` string, and a
  placeholder Upstash URL/token that ignored the real values already sitting
  in `.env`. Everything now comes from `config.py`, which reads environment
  variables.
- **`passlib` + `bcrypt==5.0.0`** is a known incompatible combination
  (passlib 1.7.4 can't read newer bcrypt's version metadata). Replaced with
  the `bcrypt` library directly.
- **`requirements.txt`** was missing `upstash-redis` (imported in `auth.py`
  but never installed) and carried three unused Postgres drivers
  (`psycopg`, `psycopg-binary`, `psycopg2-binary`) alongside `asyncpg`, which
  is the one actually used.
- **`.gitignore` excluded `alembic.ini`** itself, which would have broken
  migrations for anyone cloning the repo fresh.
- **`Notification.is_read`** existed on the model but had no endpoint to read
  or set it. Added `GET /api/v1/notifications` and
  `PATCH /api/v1/notifications/{id}/read`.
- No CORS configuration, so a browser-based client couldn't call the API at
  all. Added, configurable via `CORS_ORIGINS`.

## Project layout

```
main.py              FastAPI app, CORS, router registration
config.py             Settings (env vars)
database.py           Async SQLAlchemy engine/session, shared Base
models.py              Service, User, Notification
schemas.py              Pydantic request/response models
security.py           Password hashing + JWT
redis_client.py       Upstash Redis client
deps.py                get_current_user
routers/
  auth.py             register / resend-otp / confirm-otp / login / me
  service.py          service registration, sending messages
  notifications.py    list / mark-read
alembic/               migrations (regenerated so they actually create tables)
vercel.json
.env.example
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env         # then fill in real values
alembic upgrade head          # creates the tables in your Postgres DB

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
   `UPSTASH_URL`, `UPSTASH_TOKEN`, `OTP_TTL_SECONDS`, `BOT_USERNAME`,
   `CORS_ORIGINS` — using your **rotated** credentials, not the old ones.
4. **Run `alembic upgrade head` yourself, from your own machine, before or
   right after the first deploy.** Vercel's build step doesn't run it
   automatically, and a serverless function is the wrong place to run
   migrations against a live database.
5. Deploy. `GET /health` should return `{"status": "ok"}`.

Database access already goes through Supabase's pgbouncer transaction pooler
(port 6543) with `NullPool` on the app side, which is the recommended setup
for short-lived serverless connections — no extra config needed for that.
