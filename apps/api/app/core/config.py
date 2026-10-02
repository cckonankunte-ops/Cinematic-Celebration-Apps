"""Application settings loaded from environment variables.

All configuration comes from the environment (or a local .env file). No secrets
live in code. See .env.example for the full list of variables.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    Phase 1 has no payment gateway, so there are no PHONEPE_* / gateway variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Environment ---
    ENVIRONMENT: str = "local"  # local | staging | production

    # --- Database ---
    # e.g. postgresql+psycopg://user:pass@localhost:5432/cinematic
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/cinematic"
    DB_POOL_SIZE: int = 3
    DB_MAX_OVERFLOW: int = 2

    # --- Auth / JWT ---
    JWT_SECRET: str = "change-me-in-env"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 8

    # --- CORS (explicit allowlist; never "*") ---
    # Comma-separated list of allowed origins for the admin panel and customer site.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:4321"

    # --- Booking lifecycle ---
    PENDING_HOLD_MINUTES: int = 120

    # --- Manual payment (Phase 1) ---
    MANUAL_UPI_VPA: str = "cinematic@upi"

    # --- Email (transactional SMTP) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "bookings@cinematiccelebration.in"
    BUSINESS_EMAIL: str = "owner@cinematiccelebration.in"

    # --- Cloudflare R2 (S3-compatible) ---
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_PUBLIC_BUCKET: str = "cinematic-public"
    R2_PRIVATE_BUCKET: str = "cinematic-backups"
    IMG_CDN_DOMAIN: str = "img.cinematiccelebration.in"

    @property
    def cors_origins(self) -> list[str]:
        """Parse the comma-separated CORS allowlist into a list."""
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
