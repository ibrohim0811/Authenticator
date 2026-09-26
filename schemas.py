import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ---------- Users / Auth ----------

class RegisterSchema(BaseModel):
    full_name: str
    phone_number: str
    password: str


class ResendOTPSchema(BaseModel):
    phone_number: str


class ConfirmOTPSchema(BaseModel):
    phone_number: str
    otp_code: str
    device_token: str | None = None


class LoginSchema(BaseModel):
    phone_number: str
    password: str
    device_token: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone_number: str


class TokenSchema(BaseModel):
    status: str = "success"
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Services ----------

class RegisterServiceSchema(BaseModel):
    name: str        # short identifier, e.g. "jamgarma_app"
    title: str       # full organization name
    logo_url: str | None = None
    about: str | None = None


class SendMessageSchema(BaseModel):
    service_id: uuid.UUID
    token: str
    user_phone: str
    message: str


# ---------- Notifications ----------

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    message: str
    is_read: bool
    sent_at: datetime
