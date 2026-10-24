import logging
import asyncio
from firebase_admin import messaging

logger = logging.getLogger(__name__)

# DIQQAT: bu yerda firebase_admin.initialize_app() CHAQIRILMAYDI.
# Firebase faqat main.py ichida, service account bilan ishga tushiriladi.


async def send_fcm_notification(
    device_token: str,
    title: str,
    body: str,
    extra_data: dict | None = None,
) -> tuple[bool, str | None]:
    """FCM orqali push yuboradi. (muvaffaqiyatli_mi, xato_matni) qaytaradi."""
    try:
        formatted_data = {}
        if extra_data:
            formatted_data = {str(k): str(v) for k, v in extra_data.items() if v is not None}

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=formatted_data,
            token=device_token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    default_sound=True,
                ),
            ),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", content_available=True)
                ),
            ),
        )

        response = await asyncio.to_thread(messaging.send, message)
        logger.info(f"FCM xabari yuborildi. ID: {response}")
        return True, None
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        logger.error(f"FCM xabarini yuborishda xatolik: {err}")
        return False, err