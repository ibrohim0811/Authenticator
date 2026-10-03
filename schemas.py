import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl, Field, field_validator

# ---------- Users / Auth ----------

class RegisterSchema(BaseModel):
    full_name: str
    phone_number: str
    password: str
    device_token: str | None = None


class LoginSchema(BaseModel):
    phone_number: str
    password: str
    device_token: str | None = None


class RefreshTokenSchema(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone_number: str


class TokenSchema(BaseModel):
    status: str = "success"
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Services ----------

class ServiceResponseSchema(BaseModel):
    id: uuid.UUID
    name: str
    title: str
    logo_url: str | None = None
    about: str | None = None
    token: str

    model_config = ConfigDict(from_attributes=True)


class RegisterServiceResponse(BaseModel):
    status: str
    service_id: str
    token: str


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
