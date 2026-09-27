"""
Password hashing and JWT helpers.

Uses `bcrypt` directly (rather than passlib) to avoid the well-known
passlib 1.7.4 / bcrypt 4.1+ incompatibility, and PyJWT (which is what was
actually pinned in requirements.txt).

Two kinds of JWT are issued:
  - access token  (short-lived-ish, sent on every request, "type": "access")
  - refresh token (longer-lived, only sent to /refresh, "type": "refresh")

The "type" claim keeps them from being interchangeable: a refresh token
can't be used as a Bearer token, and an access token can't be used to
mint new tokens at /refresh.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import settings


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ---------- Refresh-token storage helper ----------
# Refresh tokens are stored in the DB as a SHA-256 hash (not bcrypt: this is
# a lookup/compare of a high-entropy random-looking token, not a low-entropy
# human password, so a fast hash is fine and avoids bcrypt's 72-byte input
# truncation).

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------- JWTs ----------

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError (caught by the caller) if the token is invalid or expired.

    Does not check the "type" claim itself — callers must check payload["type"]
    for the kind of token they expect (access vs refresh).
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
