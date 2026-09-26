import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Notification, Service, User
from schemas import RegisterServiceSchema, SendMessageSchema

router = APIRouter(prefix="/api/v1", tags=["services"])


@router.post("/services/register")
async def register_service(payload: RegisterServiceSchema, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Service).where(Service.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bunday nomli servis allaqachon ro'yxatdan o'tgan")

    generated_token = f"srv_token_{secrets.token_hex(24)}"

    new_service = Service(
        name=payload.name,
        title=payload.title,
        logo_url=payload.logo_url,
        about=payload.about,
        token=generated_token,
    )
    db.add(new_service)
    await db.commit()
    await db.refresh(new_service)

    return {"status": "success", "service_id": str(new_service.id), "token": new_service.token}


@router.post("/messages/send")
async def send_message(payload: SendMessageSchema, db: AsyncSession = Depends(get_db)):
    query_service = select(Service).where(
        Service.id == payload.service_id,
        Service.token == payload.token,
        Service.is_active == True,  # noqa: E712
    )
    service = (await db.execute(query_service)).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yaroqsiz service_id yoki token!")

    query_user = select(User).where(User.phone_number == payload.user_phone)
    user = (await db.execute(query_user)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ushbu telefon raqamli foydalanuvchi topilmadi")

    notification = Notification(user_id=user.id, service_id=service.id, message=payload.message)
    db.add(notification)
    await db.commit()

    # Push-notification dispatch (APNs/FCM etc.) would go here if user.device_token is set.

    return {"status": "success", "message": "Xabar yetkazildi"}
