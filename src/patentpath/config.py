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

    # LLM providers (Day 8).
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_primary_model: str = "gemini-3.8-flash"
    llm_fallback_model: str = "openai/gpt-oss-20b"
    # Both providers speak the OpenAI API, so any compatible server works.
    llm_primary_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_fallback_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_seconds: float = 60.0
    usd_inr: float = 95.0  # rupees per US dollar, for cost estimates
    prompts_dir: Path = Path("prompts")

    # Queue and worker (Day 10). One Redis; the worker is a second process
    redis_url: str = "redis://localhost:6379"
    manifest_file: Path = Path("data/manifest.jsonl")
    admin_token: str = ""
    worker_in_api: bool = False
    ingest_concurrency: int = 2
    ingest_rpm: float = 12.0
    ingest_job_timeout: int = 60
    ingest_max_tries: int = 3

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
