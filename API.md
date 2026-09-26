# Authenticator API Documentation

Phone-number authentication service with Telegram-bot-delivered OTP, JWT
sessions, and a push-notification API for partner services.

**Base URL**

| Environment | URL |
|---|---|
| Local | `http://127.0.0.1:8000` |
| Production | `https://<your-vercel-project>.vercel.app` |

All request/response bodies are JSON (`Content-Type: application/json`).
Interactive Swagger UI is available at `/docs`, and the raw OpenAPI schema at
`/openapi.json`, on both environments.

---

## Contents

1. [Authentication](#authentication)
2. [Users](#users)
   - [Register](#1-register)
   - [Resend OTP](#2-resend-otp)
   - [Confirm OTP](#3-confirm-otp)
   - [Login](#4-login)
   - [Current user](#5-current-user)
3. [Services](#services)
   - [Register a service](#1-register-a-service)
   - [Send a message](#2-send-a-message)
4. [Notifications](#notifications)
   - [List notifications](#1-list-notifications)
   - [Mark as read](#2-mark-as-read)
5. [Health](#health)
6. [Error format](#error-format)
7. [Status codes](#status-codes)

---

## Authentication

Two separate credentials are used in this API, for two different callers:

| Credential | Who uses it | Where |
|---|---|---|
| **JWT access token** | End users (mobile/web app) | `Authorization: Bearer <token>` header |
| **Service token** | Partner services sending notifications | In the request body, alongside `service_id` |

A JWT is issued by [Confirm OTP](#3-confirm-otp) or [Login](#4-login) and is
valid for `ACCESS_TOKEN_EXPIRE_DAYS` days (30 by default). Send it on every
endpoint marked 🔒 below:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Users

Base path: `/api/v1/users`

### 1. Register

Starts registration for a new phone number. The account is **not** created
yet — the submitted data and a 6-digit OTP code are held in Redis for a short
time (`OTP_TTL_SECONDS`, 3 minutes by default) while the user retrieves the
code from the Telegram bot.

```
POST /api/v1/users/register
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `full_name` | string | ✅ | |
| `phone_number` | string | ✅ | Must not already belong to an existing account |
| `password` | string | ✅ | Hashed with bcrypt before storage |

```json
{
  "full_name": "Ibrohim Aliyev",
  "phone_number": "+998901234567",
  "password": "S3cur3Pass!"
}
```

**Response `200`**

```json
{
  "status": "success",
  "message": "OTP yaratildi. Telegram bot orqali kodni oling.",
  "bot_url": "https://t.me/SizningBotiningizName_bot?start=%2B998901234567"
}
```

**Errors**

| Status | Cause |
|---|---|
| `400` | Phone number already registered |

---

### 2. Resend OTP

Re-generates a code for a registration that's still pending (i.e. within the
Redis TTL window). Does not restart registration — if the window already
expired, call [Register](#1-register) again instead.

```
POST /api/v1/users/resend-otp
```

**Body**

```json
{ "phone_number": "+998901234567" }
```

**Response `200`**

```json
{
  "status": "success",
  "message": "Yangi OTP kod yuborildi.",
  "bot_url": "https://t.me/SizningBotiningizName_bot?start=%2B998901234567"
}
```

**Errors**

| Status | Cause |
|---|---|
| `400` | No pending registration found for this number (expired or never started) |

---

### 3. Confirm OTP

Verifies the code, creates the user in Postgres, and returns a JWT — the
user is logged in immediately after registering.

```
POST /api/v1/users/confirm-otp
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `phone_number` | string | ✅ | |
| `otp_code` | string | ✅ | 6 digits |
| `device_token` | string | ❌ | Push-notification device token, stored on the user |

```json
{
  "phone_number": "+998901234567",
  "otp_code": "482913",
  "device_token": "fcm:abcdef123456"
}
```

**Response `200`**

```json
{
  "status": "success",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "5b1f7e2a-9c3d-4e21-8a4f-2d6c1f9b7a10",
    "full_name": "Ibrohim Aliyev",
    "phone_number": "+998901234567"
  }
}
```

**Errors**

| Status | Cause |
|---|---|
| `400` | Code expired / no pending registration, or wrong code |

---

### 4. Login

```
POST /api/v1/users/login
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `phone_number` | string | ✅ | |
| `password` | string | ✅ | |
| `device_token` | string | ❌ | Updates the stored device token if provided |

```json
{
  "phone_number": "+998901234567",
  "password": "S3cur3Pass!"
}
```

**Response `200`** — same shape as [Confirm OTP](#3-confirm-otp).

**Errors**

| Status | Cause |
|---|---|
| `401` | Wrong phone number or password |

---

### 5. Current user 🔒

Returns the account tied to the bearer token — useful for the client to
verify a stored token is still valid.

```
GET /api/v1/users/me
```

**Response `200`**

```json
{
  "id": "5b1f7e2a-9c3d-4e21-8a4f-2d6c1f9b7a10",
  "full_name": "Ibrohim Aliyev",
  "phone_number": "+998901234567"
}
```

**Errors**

| Status | Cause |
|---|---|
| `401` | Missing, invalid, or expired token |

---

## Services

Base path: `/api/v1`

These endpoints are for **partner services** (e.g. a savings app, an
e-commerce app) that want to push messages to your users, not for end users
of the mobile app.

### 1. Register a service

Creates a service identity and issues a permanent `token` used to
authenticate its future calls to [Send a message](#2-send-a-message). Store
this token securely on the service's side — it is only returned once.

```
POST /api/v1/services/register
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | ✅ | Short unique identifier, e.g. `"jamgarma_app"` |
| `title` | string | ✅ | Full display name |
| `logo_url` | string | ❌ | |
| `about` | string | ❌ | |

```json
{
  "name": "jamgarma_app",
  "title": "Jamg'arma Moliya Tashkiloti MCHJ",
  "logo_url": "https://example.com/logo.png",
  "about": "Onlayn jamg'arma xizmati"
}
```

**Response `200`**

```json
{
  "status": "success",
  "service_id": "8f2a1c3d-4b5e-4f6a-9d7c-1e2b3a4c5d6e",
  "token": "srv_token_a1b2c3d4e5f6..."
}
```

**Errors**

| Status | Cause |
|---|---|
| `400` | `name` already taken |

---

### 2. Send a message

Sends a notification to a user by phone number, on behalf of a registered,
active service. The message is stored (see [Notifications](#notifications))
and, if the user has a `device_token` on file, is also eligible for push
delivery.

```
POST /api/v1/messages/send
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `service_id` | UUID | ✅ | From [Register a service](#1-register-a-service) |
| `token` | string | ✅ | The service's token |
| `user_phone` | string | ✅ | Recipient's phone number |
| `message` | string | ✅ | |

```json
{
  "service_id": "8f2a1c3d-4b5e-4f6a-9d7c-1e2b3a4c5d6e",
  "token": "srv_token_a1b2c3d4e5f6...",
  "user_phone": "+998901234567",
  "message": "To'lovingiz muvaffaqiyatli amalga oshirildi."
}
```

**Response `200`**

```json
{ "status": "success", "message": "Xabar yetkazildi" }
```

**Errors**

| Status | Cause |
|---|---|
| `401` | Invalid `service_id`/`token`, or service is inactive |
| `404` | No user with that phone number |

---

## Notifications

Base path: `/api/v1/notifications` — all endpoints require a user's bearer
token and only ever return that user's own notifications.

### 1. List notifications 🔒

```
GET /api/v1/notifications
```

**Response `200`**

```json
[
  {
    "id": "1c2d3e4f-5a6b-7c8d-9e0f-1a2b3c4d5e6f",
    "service_id": "8f2a1c3d-4b5e-4f6a-9d7c-1e2b3a4c5d6e",
    "message": "To'lovingiz muvaffaqiyatli amalga oshirildi.",
    "is_read": false,
    "sent_at": "2026-09-26T14:02:11.482913+00:00"
  }
]
```

Sorted newest first.

---

### 2. Mark as read 🔒

```
PATCH /api/v1/notifications/{notification_id}/read
```

**Response `200`** — the updated notification, with `"is_read": true`.

**Errors**

| Status | Cause |
|---|---|
| `404` | Notification doesn't exist, or doesn't belong to the caller |

---

## Health

```
GET /
GET /health
```

Both return `200` with a small status payload — no auth required. Useful for
uptime checks and confirming a deploy is live.

```json
{ "status": "ok" }
```

---

## Error format

Every error follows FastAPI's default shape:

```json
{ "detail": "Telefon raqam yoki parol noto'g'ri!" }
```

## Status codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request — validation failed at the business-logic level (duplicate, expired, wrong code) |
| `401` | Missing/invalid credentials (JWT or service token) |
| `404` | Resource not found |
| `422` | Request body failed schema validation (missing/malformed field) |