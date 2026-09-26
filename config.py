"""
Central application configuration.

Everything here is read from environment variables (via a local .env file
during development, and via the Vercel dashboard's Environment Variables
in production). Nothing sensitive is hardcoded in source anymore.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    DATABASE_URL: str

    # --- Auth / JWT ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30

    # --- Upstash Redis (used to store short-lived OTP codes) ---
    UPSTASH_URL: str
    UPSTASH_TOKEN: str
    OTP_TTL_SECONDS: int = 180

    # --- Telegram bot used for OTP delivery ---
    BOT_USERNAME: str = "SizningBotiningizName_bot"

    # --- Misc ---
    CORS_ORIGINS: str = "*"  # comma-separated list, or "*" for all
    DEBUG: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
