import os
import json
import tempfile

import firebase_admin
from firebase_admin import credentials
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 1) FIREBASE — routerlar import qilinishidan OLDIN ishga tushadi
if not firebase_admin._apps:
    firebase_config_str = os.getenv("FIREBASE_CONFIG_JSON")
    if firebase_config_str:
        cred = credentials.Certificate(json.loads(firebase_config_str))  # Vercel
    else:
        cred = credentials.Certificate("first-public-login-1dfc7d602759.json")  # lokal
    firebase_admin.initialize_app(cred)

# 2) Endi routerlarni import qilamiz
from config import settings  # noqa: E402
from routers import service, auth, notifications  # noqa: E402

app = FastAPI(title="Authenticator by iDev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.environ.get("VERCEL"):
    UPLOAD_DIR = tempfile.gettempdir()
else:
    UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

app.include_router(auth.router)
app.include_router(service.router)
app.include_router(notifications.router)


@app.get("/")
async def welcome():
    return {"project": "Authenticator by iDev", "status": "Working 200 OK"}


@app.get("/health")
async def health():
    return {"status": "ok"}