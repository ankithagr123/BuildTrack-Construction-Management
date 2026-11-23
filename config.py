"""BuildTrack Flask application configuration."""
from __future__ import annotations
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Base configuration shared by all environments."""
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    DATABASE_PATH: str = str(BASE_DIR / "database" / "buildtrack.sqlite3")
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 5001
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_REFRESH_EACH_REQUEST = True
    JSON_SORT_KEYS: bool = False


class DevelopmentConfig(Config):
    DEBUG: bool = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "buildtrack-local-development-key-change-me")


class ProductionConfig(Config):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True


config_by_name: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}

