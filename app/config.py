from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SECRET = "dev-only-change-me-please-use-a-long-random-string"


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FeastFit"
    app_version: str = "1.0.0"
    environment: str = "development"  # development | testing | production

    secret_key: str = DEFAULT_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    password_iterations: int = 390_000

    database_url: str = "sqlite:///./feastfit.db"

    upload_dir: str = "uploads"
    max_upload_mb: int = 8
    min_image_width: int = 600
    min_image_height: int = 400

    admin_email: str = ""
    cors_origins: str = ""

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
