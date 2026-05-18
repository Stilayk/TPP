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
    # Max-Age cookie сессии (секунды). 1209600 ≈ 14 суток.
    SESSION_MAX_AGE_SECONDS: int = 1209600

    BOOTSTRAP_ADMIN_USERNAME: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    BOOTSTRAP_ADMIN_FULLNAME: str = ""

    PORT: int = 8000
    CORS_ALLOW_ORIGINS: str = ""  # comma-separated
    N8N_WEBHOOK_URL: str = ""
    N8N_WEBHOOK_TIMEOUT_SEC: int = 5
    # Отправка JSON в n8n при dispatch уведомлений о дежурствах (по умолчанию выключено; только Битрикс).
    N8N_DUTY_WEBHOOK_ENABLED: bool = False

    # Часовой пояс для встроенного планировщика уведомлений (IANA); эталон для дежурств — МСК
    TZ: str = "Europe/Moscow"

    # Битрикс24: базовый URL входящего вебхука (…/rest/<user>/<token>/), без метода в конце.
    BITRIX_INCOMING_WEBHOOK_URL: str = ""
    # Общий чат для дубля при старте слота: число 2237493 → chat2237493; см. bitrix_notify.normalize_bitrix_chat_dialog_id
    BITRIX_NOTIFY_DIALOG_ID: str = ""
    BITRIX_WEBHOOK_TIMEOUT_SEC: int = 10

    # Публичная ссылка из модалки «Выход сотрудника» (QR): срок хранения текста на сервере, секунды.
    EE_INSTRUCTION_SHARE_TTL_SECONDS: int = 7 * 24 * 3600


settings = Settings()
