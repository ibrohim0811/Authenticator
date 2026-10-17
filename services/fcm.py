import logging
import asyncio
import firebase_admin
from firebase_admin import messaging

logger = logging.getLogger(__name__)

# Firebase App allaqachon initialize bo'lmagan bo'lsa, ishga tushiramiz
if not firebase_admin._apps:
    firebase_admin.initialize_app()


async def send_fcm_notification(device_token: str, title: str, body: str) -> bool:
    """FCM orqali mobil qurilmaga darhol keladigan yuqori prioritetli push notification yuboradi."""
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=device_token,
            # Android uchun telefonni darhol uyg'otuvchi yuqori prioritet
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    default_sound=True,
                ),
            ),
            # iOS (APNs) uchun yuqori prioritet va fonda ishlash sozlamasi
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        content_available=True,  # Background update/silent push uchun
                    )
                ),
            ),
        )
        
        # messaging.send sinxron ishlagani uchun bloklab qo'ymasligi uchun uni to_thread da ishlatish ham tavsiya qilinadi
        response = await asyncio.to_thread(messaging.send, message)
        logger.info(f"FCM xabari muvaffaqiyatli yuborildi. ID: {response}")
        return True

    except Exception as e:
        logger.error(f"FCM xabar yuborishda xatolik yuz berdi: {e}")
        return False