import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import get_current_user
from models import User
from schemas import (
    LoginSchema,
    RefreshTokenSchema,
    RegisterSchema,
    TokenSchema,
    UserOut,
)
from security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/api/v1/users", tags=["auth"])


async def _issue_tokens(user: User, db: AsyncSession) -> TokenSchema:
    """Mint a fresh access/refresh pair and persist the refresh token's hash.

    Storing the hash (and overwriting it every call) means only the most
    recently issued refresh token is valid — using /refresh rotates it, so
    a leaked, already-superseded refresh token stops working.
    """
    access_token = create_access_token(data={"sub": str(user.id), "phone_number": user.phone_number})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    user.refresh_token_hash = hash_token(refresh_token)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenSchema(access_token=access_token, refresh_token=refresh_token, user=UserOut.model_validate(user))


# 1. REGISTER — creates the user immediately, no OTP/SMS/Telegram step at all
@router.post("/register", response_model=TokenSchema)
async def register_user(payload: RegisterSchema, db: AsyncSession = Depends(get_db)):
    existing_user = await db.execute(select(User).where(User.phone_number == payload.phone_number))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ushbu telefon raqam allaqachon ro'yxatdan o'tgan!")

    new_user = User(
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        hashed_password=hash_password(payload.password),
        device_token=payload.device_token,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return await _issue_tokens(new_user, db)


# 2. LOGIN
@router.post("/login", response_model=TokenSchema)
async def login_user(payload: LoginSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone_number == payload.phone_number))
    user = result.scalar_one_or_none()

    # 1. Agar foydalanuvchi bazada umumiy yo'q bo'lsa -> 404
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bunday telefon raqam avval ro'yxatdan o'tmagan!"
        )

    # 2. Parol noto'g'ri bo'lsa -> 401
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telefon raqam yoki parol noto'g'ri!",
        )

    if payload.device_token:
        user.device_token = payload.device_token

    return await _issue_tokens(user, db)
# 3. REFRESH — exchange a still-valid refresh token for a brand-new access
#    + refresh pair (rotation: the old refresh token is immediately invalid).
@router.post("/refresh", response_model=TokenSchema)
async def refresh_tokens(payload: RefreshTokenSchema, db: AsyncSession = Depends(get_db)):
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token yaroqsiz yoki muddati o'tgan!",
    )

    try:
        token_payload = decode_token(payload.refresh_token)
    except jwt.PyJWTError:
        raise invalid

    if token_payload.get("type") != "refresh":
        raise invalid

    user_id = token_payload.get("sub")
    if user_id is None:
        raise invalid

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise invalid

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user or not user.refresh_token_hash:
        raise invalid

    if user.refresh_token_hash != hash_token(payload.refresh_token):
        # Either an old, already-rotated token, or one that was never issued.
        raise invalid

    return await _issue_tokens(user, db)

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Foydalanuvchini tizimdan chiqaradi va DB'dagi refresh token hashini tozalaydi.
    """
    current_user.refresh_token_hash = None
    db.add(current_user)
    await db.commit()
    
    return {"detail": "Tizimdan muvaffaqiyatli chiqildi"}

# 4. ME — who am I (useful for the client to verify a stored token)
@router.get("/me", response_model=UserOut)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
