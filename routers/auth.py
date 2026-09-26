import json
import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from deps import get_current_user
from models import User
from redis_client import redis_client
from schemas import (
    ConfirmOTPSchema,
    LoginSchema,
    RegisterSchema,
    ResendOTPSchema,
    TokenSchema,
    UserOut,
)
from security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/users", tags=["auth"])


def _otp_key(phone_number: str) -> str:
    return f"otp:{phone_number}"


# 1. REGISTER — stash pending signup + OTP in Redis, user tells the bot the code
@router.post("/register")
async def register_user(payload: RegisterSchema, db: AsyncSession = Depends(get_db)):
    existing_user = await db.execute(select(User).where(User.phone_number == payload.phone_number))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ushbu telefon raqam allaqachon ro'yxatdan o'tgan!")

    otp_code = f"{random.randint(100000, 999999)}"
    pending_data = {
        "full_name": payload.full_name,
        "phone_number": payload.phone_number,
        "hashed_password": hash_password(payload.password),
        "otp_code": otp_code,
    }
    redis_client.set(_otp_key(payload.phone_number), json.dumps(pending_data), ex=settings.OTP_TTL_SECONDS)

    return {
        "status": "success",
        "message": "OTP yaratildi. Telegram bot orqali kodni oling.",
        "bot_url": f"https://t.me/{settings.BOT_USERNAME}?start={payload.phone_number}",
    }


# 2. RESEND OTP — regenerate a code for a signup that's already pending in Redis
@router.post("/resend-otp")
async def resend_otp(payload: ResendOTPSchema):
    key = _otp_key(payload.phone_number)
    cached = redis_client.get(key)
    if not cached:
        raise HTTPException(
            status_code=400,
            detail="Faol so'rov topilmadi. Avval /register orqali ro'yxatdan o'tishni boshlang.",
        )

    data = json.loads(cached)
    data["otp_code"] = f"{random.randint(100000, 999999)}"
    redis_client.set(key, json.dumps(data), ex=settings.OTP_TTL_SECONDS)

    return {
        "status": "success",
        "message": "Yangi OTP kod yuborildi.",
        "bot_url": f"https://t.me/{settings.BOT_USERNAME}?start={payload.phone_number}",
    }


# 3. CONFIRM OTP — verify the code, create the user in Postgres, issue a JWT
@router.post("/confirm-otp", response_model=TokenSchema)
async def confirm_otp(payload: ConfirmOTPSchema, db: AsyncSession = Depends(get_db)):
    key = _otp_key(payload.phone_number)
    cached = redis_client.get(key)
    if not cached:
        raise HTTPException(status_code=400, detail="Kod muddati o'tgan yoki so'rov topilmadi!")

    data = json.loads(cached)
    if data["otp_code"] != payload.otp_code:
        raise HTTPException(status_code=400, detail="Kiritilgan OTP kod noto'g'ri!")

    new_user = User(
        full_name=data["full_name"],
        phone_number=data["phone_number"],
        hashed_password=data["hashed_password"],
        device_token=payload.device_token,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    redis_client.delete(key)

    access_token = create_access_token(data={"sub": str(new_user.id), "phone_number": new_user.phone_number})
    return TokenSchema(access_token=access_token, user=UserOut.model_validate(new_user))


# 4. LOGIN
@router.post("/login", response_model=TokenSchema)
async def login_user(payload: LoginSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone_number == payload.phone_number))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telefon raqam yoki parol noto'g'ri!",
        )

    if payload.device_token:
        user.device_token = payload.device_token
        await db.commit()

    access_token = create_access_token(data={"sub": str(user.id), "phone_number": user.phone_number})
    return TokenSchema(access_token=access_token, user=UserOut.model_validate(user))


# 5. ME — who am I (useful for the client to verify a stored token)
@router.get("/me", response_model=UserOut)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
