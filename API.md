# Authenticator API Documentation

Phone-number authentication service with JWT access + refresh tokens, and a
push-notification API for partner services.

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
   - [Login](#2-login)
   - [Refresh](#3-refresh)
   - [Current user](#4-current-user)
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

Three separate credentials are used in this API:

| Credential | Who uses it | Where |
|---|---|---|
| **JWT access token** | End users (mobile/web app) | `Authorization: Bearer <token>` header |
| **JWT refresh token** | End users, only against `/refresh` | Request body |
| **Service token** | Partner services sending notifications | In the request body, alongside `service_id` |

[Register](#1-register) and [Login](#2-login) both return an
**access token** and a **refresh token**:

- The **access token** is valid for `ACCESS_TOKEN_EXPIRE_DAYS` days (30 by
  default) and is what you send on every 🔒 endpoint below:

  ```
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```

- The **refresh token** is valid for `REFRESH_TOKEN_EXPIRE_DAYS` days (60 by
  default) and is used only to get a new access/refresh pair via
  [Refresh](#3-refresh) once the access token is close to (or already)
  expired — without asking the user to log in again.

Refresh tokens **rotate**: every call to `/refresh` returns a brand-new
refresh token and immediately invalidates the previous one (the server only
keeps a hash of the single most-recently-issued refresh token per user). A
stolen, already-used refresh token cannot be replayed. There is no OTP, SMS,
or Telegram step anywhere in this flow — registration and login are
immediate.

---

## Users

Base path: `/api/v1/users`

### 1. Register

Creates the account immediately — full name, phone number and password are
all that's required. No OTP is generated or sent anywhere.

```
POST /api/v1/users/register
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `full_name` | string | ✅ | |
| `phone_number` | string | ✅ | Must not already belong to an existing account |
| `password` | string | ✅ | Hashed with bcrypt before storage |
| `device_token` | string | ❌ | Push-notification device token, stored on the user |

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
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
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
| `400` | Phone number already registered |

---

### 2. Login

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

**Response `200`** — same shape as [Register](#1-register). A new
access/refresh pair is issued and replaces any previous refresh token for
this user.

**Errors**

| Status | Cause |
|---|---|
| `401` | Wrong phone number or password |

---

### 3. Refresh

Exchanges a still-valid, not-yet-superseded refresh token for a brand-new
access/refresh pair. Call this when the access token has expired (or is
about to) instead of sending the user back through [Login](#2-login).

```
POST /api/v1/users/refresh
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `refresh_token` | string | ✅ | The refresh token from Register/Login/a previous Refresh |

```json
{ "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

**Response `200`** — same shape as [Register](#1-register): a new
`access_token` **and** a new `refresh_token`. The old refresh token stops
working immediately (rotation).

**Errors**

| Status | Cause |
|---|---|
| `401` | Refresh token missing/invalid/expired, not of type `refresh`, or already rotated/superseded |

---

### 4. Current user 🔒

Returns the account tied to the bearer access token — useful for the client
to verify a stored token is still valid.

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
| `401` | Missing, invalid, or expired access token (a refresh token here is also rejected) |

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
access token and only ever return that user's own notifications.

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
| `400` | Bad request — validation failed at the business-logic level (e.g. duplicate phone number) |
| `401` | Missing/invalid credentials (access token, refresh token, or service token) |
| `404` | Resource not found |
| `422` | Request body failed schema validation (missing/malformed field) |