import asyncio
from firebase_admin import messaging
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal  # O'zingizning bazadan sessiya ochuvchi fabrikangiz
from models import User
from sqlalchemy.future import select


async def process_broadcast(db_url_or_session, title: str, message: str):
  """Fon rejimida barcha foydalanuvchilarga xabar tarqatuvchi funksiya"""
  # Eslatma: Background task ichida yangi DB sessiyasini ochish kerak bo'ladi,
  # chunki so'rov sessiyasi tugab bo'lgan bo'lishi mumkin.
  # Bu yerda oddiy mantiq ko'rsatilgan:
  pass

async def send_fcm_notification(device_token: str, title: str, body: str) -> bool:
    """Bitta qurilmaga FCM orqali yuqori prioritetli push xabar yuborish"""
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=device_token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidConfig(sound="default"),
            ),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", content_available=True)
                ),
            ),
        )
        # Firebase sinxron ishlagani uchun asyncio.to_thread orqali asinxronlashtiramiz
        await asyncio.to_thread(messaging.send, message)
        return True
    except Exception as e:
        print(f"FCM xatoligi ({device_token}): {e}")
        return False

async def process_mass_push(title: str, message: str):
    """Fon rejimida barcha foydalanuvchilarning qurilmalariga xabar tarqatish"""
    # Fon vazifasi uchun alohida DB sessiyasini ochamiz
    async with AsyncSessionLocal() as session:
        try:
            # Bazadan barcha device_token mavjud userlarni olamiz
            result = await session.execute(
                select(User.device_token).where(
                    User.device_token.is_not(None), 
                    User.device_token != ""
                )
            )
            device_tokens = result.scalars().all()

            if not device_tokens:
                return

            # Har bir tokenga navbatma-navbat yoki yig'ilgan holda push yuboramiz
            for token in device_tokens:
                await send_fcm_notification(token, title, message)
                
        except Exception as e:
            print(f"Background task xatoligi: {e}")