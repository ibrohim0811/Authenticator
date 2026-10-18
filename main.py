import os
import tempfile
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import service
from routers import auth
from routers import notifications

import json
import os
import firebase_admin
from firebase_admin import credentials

if not firebase_admin._apps:
    # Vercel muhit o'zgaruvchisidan JSON matnni olamiz
    firebase_config_str = os.getenv("FIREBASE_CONFIG_JSON")
    
    if firebase_config_str:
        # Agar Vercel'da bo'lsa, matnni JSON dictionary ga o'tkazib ulaymiz
        cred_dict = json.loads(firebase_config_str)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    else:
        # Agar lokal kompyuterda ishlatayotgan bo'lsangiz, oddiy fayldan o'qiydi
        cred = credentials.Certificate("first-public-login-1dfc7d602759.json")
        firebase_admin.initialize_app(cred)

app = FastAPI(title="Authenticator by iDev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if os.environ.get("VERCEL"):
    UPLOAD_DIR = tempfile.gettempdir() # /tmp
else:
    UPLOAD_DIR = "uploads"

# 2. Papka yo'q bo'lsa yaratamiz
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 3. StaticFiles ni dynamic papka yo'li bilan ulash
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
