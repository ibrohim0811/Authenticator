import logging
import asyncio
import firebase_admin
from firebase_admin import messaging

logger = logging.getLogger(__name__)

# Firebase App allaqachon initialize bo'lmagan bo'lsa, ishga tushiramiz
if not firebase_admin._apps:
    firebase_admin.initialize_app()


async def send_fcm_notification(
    device_token: str, 
    title: str, 
    body: str, 
    extra_data: dict = None
) -> bool:
    """FCM orqali mobil qurilmaga darhol keladigan yuqori prioritetli push notification yuboradi."""
    try:
        # data qiymatlari faqat string (matn) bo'lishi kerak, shuning uchun barchasini str ga o'tkazib olamiz
        formatted_data = {}
        if extra_data:
            formatted_data = {str(k): str(v) for k, v in extra_data.items() if v is not None}

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            # Qo'shimcha ma'lumotlarni shu yerga qo'shamiz
            data=formatted_data,
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
        
        response = await asyncio.to_thread(messaging.send, message)
        logger.info(f"FCM xabari muvaffaqiyatli yuborildi. ID: {response}")
        return True
    except Exception as e:
        logger.error(f"FCM xabarini yuborishda xatolik: {e}")
        return False