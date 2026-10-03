# Authenticator API Documentation

Phone-number authentication service with **JWT access + refresh tokens**, plus a
**notification API** that lets partner services send messages to your users.

> **Version:** v1 · **Last verified against source:** 2026-10-03

---

## Table of contents

1. [Quick start (for frontend / mobile)](#1-quick-start-for-frontend--mobile)
2. [General conventions](#2-general-conventions)
3. [Authentication model](#3-authentication-model)
4. [Users API](#4-users-api)
   - [Register](#41-register)
   - [Login](#42-login)
   - [Refresh tokens](#43-refresh-tokens)
   - [Current user](#44-current-user-)
5. [Notifications API](#5-notifications-api)
   - [List notifications](#51-list-notifications-)
   - [Mark as read](#52-mark-as-read-)
6. [Services API (partner services)](#6-services-api-partner-services)
   - [Register a service](#61-register-a-service)
   - [Send a message](#62-send-a-message)
7. [Health checks](#7-health-checks)
8. [Data models](#8-data-models)
9. [Errors](#9-errors)
10. [Troubleshooting `401 Unauthorized`](#10-troubleshooting-401-unauthorized)
11. [Frontend integration example](#11-frontend-integration-example)

Legend: 🔒 = requires `Authorization: Bearer <access_token>`.

---

## 1. Quick start (for frontend / mobile)

```text
┌──────────┐   POST /api/v1/users/register  or  /login      ┌────────┐
│  Client  │ ─────────────────────────────────────────────▶ │  API   │
│          │ ◀───────────────  access_token + refresh_token │        │
│          │                                                │        │
│          │   GET /api/v1/users/me                         │        │
│          │   Authorization: Bearer <access_token>  ─────▶ │        │
│          │                                                │        │
│          │   access token expired (401)?                  │        │
│          │   POST /api/v1/users/refresh {refresh_token} ─▶│        │
│          │ ◀───────────  NEW access_token + refresh_token │        │
└──────────┘                                                └────────┘
```

**The 5 rules that avoid 95% of integration problems:**

1. Send **JSON** (`Content-Type: application/json`), **not** form data.
   Login does **not** use `username`/`password` — the fields are `phone_number` and `password`.
2. Send the phone number in **exactly the same format** on register and login
   (recommended: `+998901234567`). The server does **not** normalize it
   — see [Phone number format](#phone-number-format).
3. Send the **access** token as `Authorization: Bearer <access_token>`
   (never the refresh token, no quotes, no missing `Bearer ` prefix).
4. **Always save the newest `refresh_token`** — every `/refresh` (and every login)
   invalidates the previous one.
5. Call URLs **without a trailing slash** (`/api/v1/notifications`, not `/api/v1/notifications/`).

---

## 2. General conventions

### Base URL

| Environment | URL |
|---|---|
| Local | `http://127.0.0.1:8000` |
| Production | `https://<your-vercel-project>.vercel.app` |

Interactive Swagger UI: `GET /docs` · Raw OpenAPI schema: `GET /openapi.json`

### Requests & responses

| Item | Value |
|---|---|
| Format | JSON only (`Content-Type: application/json`) |
| Success status | `200 OK` for every endpoint (including register) |
| IDs | UUID v4 strings |
| Timestamps | ISO 8601, UTC (e.g. `2026-09-26T14:02:11.482913+00:00`) |
| CORS | Controlled by the `CORS_ORIGINS` env var (`*` by default) |
| Error messages | The `detail` text is in **Uzbek** (see [Errors](#9-errors)) |

### Phone number format

The phone number is stored and compared as an **exact string** — there is no
trimming, no removal of spaces and no country-code normalization on the server.

| Sent at register | Sent at login | Result |
|---|---|---|
| `+998901234567` | `+998901234567` | ✅ works |
| `+998901234567` | `998901234567` | ❌ `401` (different string) |
| `+998901234567` | `+998 90 123 45 67` | ❌ `401` |
| `+998901234567` | `+998901234567 ` (trailing space) | ❌ `401` |

**Recommendation:** normalize on the client before every request (digits only,
prefixed with `+`, no spaces/dashes/brackets). Max length is **20 characters**.

### Trailing slashes

`POST /api/v1/users/login/` (with `/`) does **not** return the login response —
it returns a `307` redirect to the URL without the slash. Some HTTP clients drop
the `Authorization` header or change the scheme when following redirects. Always
call the exact paths shown in this document.

---

## 3. Authentication model

The API uses three kinds of credentials:

| Credential | Used by | How it is sent |
|---|---|---|
| **Access token** (JWT) | End users (mobile / web app) | `Authorization: Bearer <access_token>` header |
| **Refresh token** (JWT) | End users, **only** for `POST /api/v1/users/refresh` | JSON body |
| **Service token** | Partner services sending notifications | JSON body (`service_id` + `token`) |

### Tokens

| | Access token | Refresh token |
|---|---|---|
| Lifetime (defaults) | **30 days** (`ACCESS_TOKEN_EXPIRE_DAYS`) | **60 days** (`REFRESH_TOKEN_EXPIRE_DAYS`) |
| Algorithm | HS256 | HS256 |
| Claims | `sub` (user id), `phone_number`, `exp`, `type: "access"` | `sub` (user id), `exp`, `type: "refresh"` |
| Accepted by | All 🔒 endpoints | `POST /users/refresh` only |

The `type` claim is enforced: a refresh token is **rejected** on 🔒 endpoints and
an access token is **rejected** on `/refresh`.

### Refresh-token rotation (important)

The server stores a hash of **one** refresh token per user — the most recently issued one.
A new refresh token is issued on **register**, **login** and **refresh**; each time,
the previous refresh token stops working immediately.

Consequences for the client:

- **Always replace the stored refresh token** with the one from the latest response.
- **Single device per user for refresh:** logging in on device B invalidates device A's
  refresh token. Device A's current *access* token keeps working until it expires,
  but once it does, device A must log in again.
- **Never run two `/refresh` calls at once.** If two requests fire in parallel with the
  same refresh token, the second one gets `401`. Queue them behind a single in-flight
  refresh (see [example](#11-frontend-integration-example)).
- There is **no OTP, SMS or Telegram step** — register and login are immediate.

---

## 4. Users API

Base path: `/api/v1/users`

### 4.1 Register

Creates the account immediately and returns tokens.

```http
POST /api/v1/users/register
Content-Type: application/json
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `full_name` | string | ✅ | Max 250 characters |
| `phone_number` | string | ✅ | Max 20 characters, must be unique. See [format](#phone-number-format) |
| `password` | string | ✅ | Max **72 bytes** (bcrypt limit). Stored as a bcrypt hash |
| `device_token` | string | ❌ | Push device token, saved on the user |

```json
{
  "full_name": "Ibrohim Aliyev",
  "phone_number": "+998901234567",
  "password": "S3cur3Pass!",
  "device_token": "fcm_device_token_here"
}
```

**Response `200`** — see [`TokenResponse`](#tokenresponse)

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

| Status | `detail` | Cause |
|---|---|---|
| `400` | `Ushbu telefon raqam allaqachon ro'yxatdan o'tgan!` | Phone number already registered |
| `422` | *(validation array)* | Missing/invalid field |

**cURL**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Ibrohim Aliyev","phone_number":"+998901234567","password":"S3cur3Pass!"}'
```

---

### 4.2 Login

```http
POST /api/v1/users/login
Content-Type: application/json
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `phone_number` | string | ✅ | Must match the registered value **exactly** |
| `password` | string | ✅ | |
| `device_token` | string | ❌ | If provided, replaces the stored device token |

```json
{
  "phone_number": "+998901234567",
  "password": "S3cur3Pass!"
}
```

**Response `200`** — same shape as [Register](#41-register). A new access/refresh
pair is issued and **replaces** the user's previous refresh token.

**Errors**

| Status | `detail` | Cause |
|---|---|---|
| `401` | `Telefon raqam yoki parol noto'g'ri!` | Phone number not found **or** wrong password (the API intentionally doesn't say which) |
| `422` | *(validation array)* | Body is not JSON / a field is missing (e.g. you sent `username` or form-data) |

> 💡 A `401` on login **always** means "no user with this exact `phone_number`,
> or the password doesn't match". Nothing else (headers, tokens, CORS) can cause it.
> See [Troubleshooting](#10-troubleshooting-401-unauthorized).

**cURL**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"+998901234567","password":"S3cur3Pass!"}'
```

---

### 4.3 Refresh tokens

Exchanges a valid refresh token for a **new** access token **and** a **new** refresh token.
Use it when the access token has expired (or is about to) instead of sending the user
back to the login screen.

```http
POST /api/v1/users/refresh
Content-Type: application/json
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `refresh_token` | string | ✅ | The **latest** refresh token you received |

```json
{ "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

**Response `200`** — same shape as [Register](#41-register). The old refresh token
stops working immediately.

**Errors**

| Status | `detail` | Cause |
|---|---|---|
| `401` | `Refresh token yaroqsiz yoki muddati o'tgan!` | Token malformed / expired / not of type `refresh` / already rotated / user logged in elsewhere |
| `422` | *(validation array)* | `refresh_token` missing |

On `401` from this endpoint, clear stored tokens and send the user to the login screen.

---

### 4.4 Current user 🔒

Returns the account that owns the access token. Handy for checking on app start
that a stored token is still valid.

```http
GET /api/v1/users/me
Authorization: Bearer <access_token>
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

| Status | `detail` | Cause |
|---|---|---|
| `401` | `Not authenticated` | `Authorization` header missing, or not in `Bearer <token>` form |
| `401` | `Token yaroqsiz yoki muddati o'tgan!` | Token invalid / expired / is a **refresh** token / user no longer exists |

Both `401` responses include the header `WWW-Authenticate: Bearer`.

---

## 5. Notifications API

Base path: `/api/v1/notifications` — every endpoint requires a user's **access
token** and only ever touches **that user's** notifications.

### 5.1 List notifications 🔒

```http
GET /api/v1/notifications
Authorization: Bearer <access_token>
```

**Response `200`** — array of [`Notification`](#notification), **newest first**
(no pagination yet — the full list is returned).

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

An empty array `[]` means the user has no notifications.

**Errors:** `401` (see [Current user](#44-current-user-)).

> ⚠️ Use `/api/v1/notifications` **without** a trailing slash — with one, the server
> answers `307` (redirect) instead of the data.

---

### 5.2 Mark as read 🔒

```http
PATCH /api/v1/notifications/{notification_id}/read
Authorization: Bearer <access_token>
```

| Path param | Type | Notes |
|---|---|---|
| `notification_id` | UUID | Notification `id` from the list |

No request body.

**Response `200`** — the updated [`Notification`](#notification) with `"is_read": true`.
Calling it again on an already-read notification is harmless.

**Errors**

| Status | `detail` | Cause |
|---|---|---|
| `401` | see above | Missing/invalid access token |
| `404` | `Bildirishnoma topilmadi` | Notification doesn't exist **or belongs to another user** |
| `422` | *(validation array)* | `notification_id` is not a valid UUID |

---

## 6. Services API (partner services)

Base path: `/api/v1`

These endpoints are for **partner backends** (e.g. a savings app, an e-commerce app)
that want to push messages to your users — **not** for the mobile/web app's end users.
Do **not** call them from the client app: the service `token` is a secret.

> ⚠️ **Current limitation:** `POST /services/register` is **not protected** — anyone
> who can reach the API can create a service and then message any registered phone
> number. An admin layer is planned (see `.TODO`); until then, treat this endpoint as
> internal and restrict access at the network level if needed.

### 6.1 Register a service

Creates a service identity and returns a permanent `token`. **The token is shown only
once** — store it securely on the partner's backend.

```http
POST /api/v1/services/register
Content-Type: application/json
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | ✅ | Short unique identifier, max 100 chars (e.g. `jamgarma_app`) |
| `title` | string | ✅ | Display name, max 255 chars |
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
  "token": "srv_token_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6"
}
```

**Errors**

| Status | `detail` | Cause |
|---|---|---|
| `400` | `Bunday nomli servis allaqachon ro'yxatdan o'tgan` | `name` already taken |
| `422` | *(validation array)* | Missing/invalid field |

---

### 6.2 Send a message

Stores a notification for the user with the given phone number, on behalf of an
active service. The user then sees it via [List notifications](#51-list-notifications-).

```http
POST /api/v1/messages/send
Content-Type: application/json
```

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `service_id` | UUID | ✅ | From [Register a service](#61-register-a-service) |
| `token` | string | ✅ | The service's token |
| `user_phone` | string | ✅ | Must match the user's registered phone **exactly** |
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

> ℹ️ **Push delivery is not implemented yet.** The message is saved and appears in the
> user's notification list, but nothing is sent to APNs/FCM even if the user has a
> `device_token`. The client must fetch notifications via the API (e.g. poll
> `GET /api/v1/notifications`).

**Errors**

| Status | `detail` | Cause |
|---|---|---|
| `401` | `Yaroqsiz service_id yoki token!` | Wrong `service_id`/`token` pair, or the service is inactive |
| `404` | `Ushbu telefon raqamli foydalanuvchi topilmadi` | No user with that phone number |
| `422` | *(validation array)* | Missing field, or `service_id` isn't a UUID |

---

## 7. Health checks

No authentication required.

```http
GET /
```

```json
{ "project": "Authenticator by iDev", "status": "Working 200 OK" }
```

```http
GET /health
```

```json
{ "status": "ok" }
```

---

## 8. Data models

### TokenResponse

Returned by **register**, **login** and **refresh**.

| Field | Type | Description |
|---|---|---|
| `status` | string | Always `"success"` |
| `access_token` | string | JWT, send as `Bearer` token |
| `refresh_token` | string | JWT, send only to `/users/refresh`. **Replace the stored one every time** |
| `token_type` | string | Always `"bearer"` |
| `user` | [`User`](#user) | The authenticated user |

### User

| Field | Type | Description |
|---|---|---|
| `id` | UUID | |
| `full_name` | string | |
| `phone_number` | string | |

### Notification

| Field | Type | Description |
|---|---|---|
| `id` | UUID | |
| `service_id` | UUID | The service that sent it |
| `message` | string | |
| `is_read` | boolean | `false` until marked as read |
| `sent_at` | datetime (UTC) | |

---

## 9. Errors

### Business errors

Errors raised by the API have this shape (`detail` is a **string**):

```json
{ "detail": "Telefon raqam yoki parol noto'g'ri!" }
```

### Validation errors (`422`)

When the body/params don't match the schema, FastAPI returns `detail` as an
**array** of objects — not a string. Make sure your client handles both shapes:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "phone_number"],
      "msg": "Field required",
      "input": { "full_name": "A" }
    }
  ]
}
```

### Status codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `307` | You used a URL with a trailing slash — the server is redirecting to the slash-less URL |
| `400` | Business-rule violation (duplicate phone number, duplicate service name) |
| `401` | Missing/invalid credentials (login, access token, refresh token or service token) |
| `404` | Resource not found |
| `422` | Request failed schema validation (missing/malformed field, body isn't JSON) |
| `500` | Server error (e.g. misconfigured environment variables / database) |

### Every error message

| Endpoint | Status | `detail` |
|---|---|---|
| `POST /users/register` | 400 | `Ushbu telefon raqam allaqachon ro'yxatdan o'tgan!` |
| `POST /users/login` | 401 | `Telefon raqam yoki parol noto'g'ri!` |
| `POST /users/refresh` | 401 | `Refresh token yaroqsiz yoki muddati o'tgan!` |
| 🔒 endpoints | 401 | `Not authenticated` (no/incorrect `Authorization` header) |
| 🔒 endpoints | 401 | `Token yaroqsiz yoki muddati o'tgan!` |
| `PATCH /notifications/{id}/read` | 404 | `Bildirishnoma topilmadi` |
| `POST /services/register` | 400 | `Bunday nomli servis allaqachon ro'yxatdan o'tgan` |
| `POST /messages/send` | 401 | `Yaroqsiz service_id yoki token!` |
| `POST /messages/send` | 404 | `Ushbu telefon raqamli foydalanuvchi topilmadi` |

---

## 10. Troubleshooting `401 Unauthorized`

**First step: read the `detail` text in the response body.** It tells you exactly where to look.

| `detail` | Endpoint | Likely cause | Fix |
|---|---|---|---|
| `Telefon raqam yoki parol noto'g'ri!` | `/login` | Phone number differs from what was used at register (`+` missing, spaces, trailing space, `0` prefix, …) | Normalize the phone number the same way in both places; log the exact string you send |
| `Telefon raqam yoki parol noto'g'ri!` | `/login` | Wrong password, or password was trimmed/modified by the input field | Compare the raw value; test the same credentials in `/docs` |
| `Telefon raqam yoki parol noto'g'ri!` | `/login` | User was registered on a **different environment** (local DB vs. production DB) | Use the same Base URL for register and login, or register again on the target environment |
| `Not authenticated` | 🔒 | No `Authorization` header, or it doesn't start with `Bearer ` | Send `Authorization: Bearer <access_token>` |
| `Token yaroqsiz yoki muddati o'tgan!` | 🔒 | Sent the **refresh** token instead of the access token | Use `access_token` for API calls |
| `Token yaroqsiz yoki muddati o'tgan!` | 🔒 | Token wrapped in quotes / contains whitespace or newline / was `JSON.stringify`-ed into storage | Store and send the raw string |
| `Token yaroqsiz yoki muddati o'tgan!` | 🔒 | Access token expired (30 days by default) | Call `/users/refresh`, then retry |
| `Token yaroqsiz yoki muddati o'tgan!` | 🔒 | Token was issued by a server with a different `SECRET_KEY` (e.g. local token used against production) | Log in against the same environment you call |
| `Refresh token yaroqsiz yoki muddati o'tgan!` | `/refresh` | Refresh token already used (rotated) — often two parallel refresh calls, or the old token was saved | Always save the newest refresh token; serialize refresh calls |
| `Refresh token yaroqsiz yoki muddati o'tgan!` | `/refresh` | The user logged in on another device (that invalidates this device's refresh token) | Send the user to the login screen |
| `Yaroqsiz service_id yoki token!` | `/messages/send` | Wrong pair or inactive service | Re-check the values returned by `/services/register` |

**Other things that look like login problems but aren't `401`:**

| Symptom | Cause |
|---|---|
| `422` on login | Body isn't JSON (form-data / `x-www-form-urlencoded`), or you sent `username` instead of `phone_number` |
| `307` on login | URL has a trailing slash (`/login/`) |
| `500` on register | Password longer than 72 bytes, or phone number longer than 20 characters (database limit) |
| Swagger "Authorize" button fails | The Authorize dialog sends a *form* to `/login`, but this endpoint accepts JSON only. Call `/login` via "Try it out", then paste the `access_token` into the Authorize dialog |

**Quick isolation test** — if this works but your app doesn't, the problem is in the client's request:

```bash
# 1. Register (once)
curl -s -X POST "$BASE/api/v1/users/register" -H "Content-Type: application/json" \
  -d '{"full_name":"Test","phone_number":"+998901234567","password":"S3cur3Pass!"}'

# 2. Login
curl -s -X POST "$BASE/api/v1/users/login" -H "Content-Type: application/json" \
  -d '{"phone_number":"+998901234567","password":"S3cur3Pass!"}'

# 3. Use the access token
curl -s "$BASE/api/v1/users/me" -H "Authorization: Bearer <access_token>"
```

---

## 11. Frontend integration example

A minimal `fetch` wrapper (JavaScript) that attaches the token, refreshes it once on
`401`, and makes sure only one refresh runs at a time.

```js
const BASE_URL = "https://<your-vercel-project>.vercel.app";

// Keep the same phone format on register AND login.
export const normalizePhone = (raw) => "+" + raw.replace(/\D/g, "");

const tokens = {
  get access() { return localStorage.getItem("access_token"); },
  get refresh() { return localStorage.getItem("refresh_token"); },
  save(data) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token); // always overwrite!
  },
  clear() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },
};

export async function login(phone, password) {
  const res = await fetch(`${BASE_URL}/api/v1/users/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number: normalizePhone(phone), password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Validation error");
  tokens.save(data);
  return data.user;
}

let refreshing = null; // single in-flight refresh

async function refreshTokens() {
  refreshing ??= fetch(`${BASE_URL}/api/v1/users/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh }),
  })
    .then(async (res) => {
      if (!res.ok) { tokens.clear(); throw new Error("SESSION_EXPIRED"); }
      tokens.save(await res.json());
    })
    .finally(() => { refreshing = null; });
  return refreshing;
}

export async function api(path, options = {}, retry = true) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
      Authorization: `Bearer ${tokens.access}`,
    },
  });

  if (res.status === 401 && retry && tokens.refresh) {
    await refreshTokens();               // throws SESSION_EXPIRED -> go to login screen
    return api(path, options, false);    // retry once with the new token
  }
  return res;
}

// Usage
// const me = await (await api("/api/v1/users/me")).json();
// const list = await (await api("/api/v1/notifications")).json();
// await api(`/api/v1/notifications/${id}/read`, { method: "PATCH" });
```

> On mobile, store tokens in the platform's secure storage (Keychain / Keystore)
> rather than plain `localStorage` / `SharedPreferences`.