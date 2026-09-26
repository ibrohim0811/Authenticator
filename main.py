from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth, notifications, service

app = FastAPI(title="Authenticator by iDev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(service.router)
app.include_router(notifications.router)


@app.get("/")
async def welcome():
    return {"project": "Authenticator by iDev", "status": "Working 200 OK"}


@app.get("/health")
async def health():
    return {"status": "ok"}
