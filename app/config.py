import os
import sys
from pathlib import Path


def is_frozen_build() -> bool:
    return getattr(sys, "frozen", False)


def is_vercel() -> bool:
    return "VERCEL" in os.environ


def get_database_url() -> str | None:
    if is_frozen_build():
        return None
    return os.environ.get("DATABASE_URL")


def get_data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data"))


def is_local_mode() -> bool:
    db_url = get_database_url()
    return not db_url or db_url.strip() == ""


def is_local_auth_mode() -> bool:
    return is_frozen_build() or is_local_mode()


def should_use_secure_cookies() -> bool:
    return not is_local_auth_mode()


def should_run_migrations_on_startup() -> bool:
    setting = os.environ.get("RUN_MIGRATIONS_ON_STARTUP")
    if setting is None:
        setting = "false" if is_vercel() else "true"
    return setting.lower() == "true"


def get_secret_key() -> str | None:
    return os.environ.get("SECRET_KEY")
