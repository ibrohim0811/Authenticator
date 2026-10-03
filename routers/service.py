import os
import uuid
import secrets
import shutil
import tempfile
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# O'zingizning modellaringiz va bog'liqliklaringizni import qiling:
from models import Service, User, UserRole, Notification
from deps import get_db, get_current_user
from schemas import RegisterServiceResponse, SendMessageSchema
from services.fcm import send_fcm_notification

router = APIRouter(prefix="/services", tags=["Services"])

# Fayllar saqlanadigan papka
UPLOAD_DIR = "uploads"
if os.environ.get("VERCEL"):
    UPLOAD_DIR = tempfile.gettempdir()  # Vercel'da bu '/tmp' bo'ladi
else:
    UPLOAD_DIR = "uploads"  # Local kompyuteringiz uchun

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/register", response_model=RegisterServiceResponse, status_code=status.HTTP_201_CREATED)
async def register_service(
    name: str = Form(..., min_length=3, max_length=50, description="Masalan: jamgarma_app"),
    title: str = Form(..., min_length=2, max_length=150),
    about: str | None = Form(None),
    logo: UploadFile | None = File(None),  # PC'dan rasm yuklash uchun
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # 1. Huquqni tekshirish (Faqat OWNER yoki ADMIN ruxsati uchun)
    if user.role != UserRole.OWNER and user.role != UserRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ushbu amalni bajarish uchun sizda yetarli huquq yo'q."
        )

    # 2. Servis nomi takrorlanmaganligini tekshirish
    stmt = select(Service).where(Service.name == name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bunday nomli servis allaqachon ro'yxatdan o'tgan."
        )

    # 3. Agar rasm yuborilgan bo'lsa, uni local diskka saqlaymiz
    logo_url = None
    if logo and logo.filename:
        # Fayl kengaytmasini aniqlash (.png, .jpg va h.k.)
        file_ext = os.path.splitext(logo.filename)[1].lower()
        if file_ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Faqat rasm fayllari (.jpg, .jpeg, .png, .webp) qabul qilinadi."
            )

        # Unikal fayl nomi beramiz
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Faylni diskka yozish
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)

        # Bazaga saqlanadigan nisbiy havola (Static files orqali ko'rish uchun)
        logo_url = f"/static/{unique_filename}"

    # 4. Servis tokenini generatsiya qilish
    generated_token = f"srv_token_{secrets.token_hex(24)}"

    # 5. Yangi servis obyektini yaratish
    new_service = Service(
        name=name,
        title=title,
        about=about,
        logo_url=logo_url,
        token=generated_token,
    )

    db.add(new_service)
    await db.commit()
    await db.refresh(new_service)

    return {
        "status": "success",
        "service_id": str(new_service.id),
        "token": new_service.token
    }

@router.post("/messages/send")
async def send_message(payload: SendMessageSchema, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != UserRole.OWNER and user.role != UserRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ushbu amalni bajarish uchun sizda yetarli huquq yo'q."
            )
    # 1. Servis va token tekshiruvi (is_active uchun # noqa siz to'g'ri SQLAlchemy 2.0 usuli)
    query_service = select(Service).where(
        Service.id == payload.service_id,
        Service.token == payload.token,
        Service.is_active,
    )
    service = (await db.execute(query_service)).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yaroqsiz service_id yoki token!")

    # 2. Foydalanuvchini izlash
    query_user = select(User).where(User.phone_number == payload.user_phone)
    user = (await db.execute(query_user)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ushbu telefon raqamli foydalanuvchi topilmadi")

    # 3. Bildirishnomani bazaga saqlash
    notification = Notification(user_id=user.id, service_id=service.id, message=payload.message)
    db.add(notification)
    await db.commit()

    # 4. FCM Push-notification yuborish
    fcm_sent = False
    if getattr(user, "device_token", None):
        fcm_sent = await send_fcm_notification(
            device_token=user.device_token,
            title=service.title if hasattr(service, "title") else service.name,
            body=payload.message,
        )

    return {
        "status": "success",
        "message": "Xabar yetkazildi",
        "push_sent": fcm_sent
    }