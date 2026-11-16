import uuid

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from database import AsyncSessionLocal
from models import User
from security import decode_token
from services.ws_manager import manager

router = APIRouter(tags=["websocket"])


async def _get_user_id(token: str) -> uuid.UUID | None:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access" or not payload.get("sub"):
            return None
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None

    # sessiyani darrov yopamiz, WebSocket ochiq tursa ham DB ulanish band bo'lmasin
    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
    return user.id if user and user.is_active else None


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket, token: str = Query(...)):
    user_id = await _get_user_id(token)
    if user_id is None:
        await websocket.close(code=1008)  # policy violation
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # clientdan "ping" keladi, ulanish tirik turadi
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, websocket)