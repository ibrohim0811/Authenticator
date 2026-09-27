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
    REFRESH_TOKEN_EXPIRE_DAYS: int = 60

    # --- Misc ---
    CORS_ORIGINS: str = "*"  # comma-separated list, or "*" for all
    DEBUG: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
