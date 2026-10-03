import os
import tempfile
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import service
from routers import auth
from routers import notifications

app = FastAPI(title="Authenticator by iDev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
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
