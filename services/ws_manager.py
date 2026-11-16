import uuid
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # bitta user bir nechta qurilmadan ulanishi mumkin
        self.active: dict[uuid.UUID, set[WebSocket]] = {}

    async def connect(self, user_id: uuid.UUID, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, set()).add(ws)

    def disconnect(self, user_id: uuid.UUID, ws: WebSocket):
        conns = self.active.get(user_id)
        if conns:
            conns.discard(ws)
            if not conns:
                self.active.pop(user_id, None)

    async def send_to_user(self, user_id: uuid.UUID, data: dict) -> int:
        sent = 0
        for ws in list(self.active.get(user_id, [])):
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                self.disconnect(user_id, ws)
        return sent

    async def broadcast(self, data: dict):
        for user_id in list(self.active.keys()):
            await self.send_to_user(user_id, data)


manager = ConnectionManager()