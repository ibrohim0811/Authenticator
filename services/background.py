import asyncio
import logging

from sqlalchemy.future import select

from database import AsyncSessionLocal
from models import User
from services.fcm import send_fcm_notification  # to'g'ri versiya

logger = logging.getLogger(__name__)


async def process_mass_push(title: str, message: str) -> tuple[int, int]:
    """Device tokeni bor barcha userlarga push yuboradi. (yuborildi, xato) qaytaradi."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.device_token).where(
                    User.device_token.is_not(None),
                    User.device_token != "",
                )
            )
            tokens = list(set(result.scalars().all()))
    except Exception as e:
        logger.error(f"Broadcast: tokenlarni olishda xatolik: {e}")
        return 0, 0

    if not tokens:
        return 0, 0

    sem = asyncio.Semaphore(10)  # bir vaqtda 10 tadan ortiq yubormaymiz

    async def _send(token: str) -> bool:
        async with sem:
            ok, err = await send_fcm_notification(token, title, message)
            if not ok:
                logger.warning(f"Broadcast FCM xatosi: {err}")
            return ok

    results = await asyncio.gather(*(_send(t) for t in tokens))
    sent = sum(1 for r in results if r)
    return sent, len(results) - sent