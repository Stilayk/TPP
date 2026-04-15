from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Обязательно: только PostgreSQL (например postgresql+psycopg://user:pass@host:5432/dbname).
    DATABASE_URL: str = ""
    EXPORTS_DIR: str = "exports"
    SESSION_SECRET: str = ""
    # В проде за HTTPS включите true — cookie сессии с флагом Secure (на HTTP локально оставьте false).
    SESSION_COOKIE_HTTPS_ONLY: bool = False

    BOOTSTRAP_ADMIN_USERNAME: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    BOOTSTRAP_ADMIN_FULLNAME: str = ""

    PORT: int = 8000
    CORS_ALLOW_ORIGINS: str = ""  # comma-separated
    N8N_WEBHOOK_URL: str = ""
    N8N_WEBHOOK_TIMEOUT_SEC: int = 5

    # Битрикс24: базовый URL входящего вебхука (…/rest/<user>/<token>/), без метода в конце.
    BITRIX_INCOMING_WEBHOOK_URL: str = ""
    # Куда писать: для лички — ID пользователя Битрикс строкой (например 6188); для чата — chatNNN.
    BITRIX_NOTIFY_DIALOG_ID: str = ""
    BITRIX_WEBHOOK_TIMEOUT_SEC: int = 10


settings = Settings()
