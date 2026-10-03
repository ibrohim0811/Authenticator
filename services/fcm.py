import logging
import firebase_admin
from firebase_admin import messaging

logger = logging.getLogger(__name__)

# Firebase App allaqachon initialize bo'lmagan bo'lsa, ADC orqali ishga tushiramiz
if not firebase_admin._apps:
    firebase_admin.initialize_app()


async def send_fcm_notification(device_token: str, title: str, body: str) -> bool:
    """FCM orqali mobil qurilmaga push notification yuboradi."""
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=device_token,
        )
        
        response = messaging.send(message)
        logger.info(f"FCM xabari muvaffaqiyatli yuborildi. ID: {response}")
        return True

    except Exception as e:
        logger.error(f"FCM xabar yuborishda xatolik yuz berdi: {e}")
        return False