"""All settings come from environment variables (or a local .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "patentpath"
    app_env: Literal["local", "ci", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    data_file: Path = Path("data/sample_records.json")
    database_url: str = "postgresql://localhost:5432/patentpath"

    # Optional Cloudflare R2 object storage.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_endpoint_url: str = ""
    r2_region: str = "auto"

    # The commit this image was built from. CI sets it.
    git_sha: str = "dev"


@lru_cache
def get_settings() -> Settings:
    """Build the settings once and reuse them."""
    return Settings()
