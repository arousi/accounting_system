from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.getenv("ACCOUNTING_SECRET_KEY", "change-this-secret-key")
    DATABASE_URL = os.getenv(
        "ACCOUNTING_DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'accounting_web.db').as_posix()}",
    )
    SESSION_DURATION_MINUTES = int(os.getenv("ACCOUNTING_SESSION_DURATION_MINUTES", "480"))
    DEFAULT_LOCALE = os.getenv("ACCOUNTING_DEFAULT_LOCALE", "ar")
    SUPPORTED_LOCALES = ("ar", "en")
    JSON_SORT_KEYS = False
