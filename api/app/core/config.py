"""Typed application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Core ----
    app_env: Literal["development", "production", "test"] = "development"
    app_secret_key: str = "dev-insecure-change-me-0000000000000000"
    public_host: str = "http://localhost:3000"
    port: int = 3000
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://ytauto:ytauto@localhost:5433/ytauto"
    redis_url: str = "redis://localhost:6380/0"
    cors_origins: str = "http://localhost:5173"

    admin_email: str = "admin@example.com"
    admin_password: Optional[str] = "admin12345"
    auth_allow_registration: bool = False  # open sign-up (first user is always allowed)

    storage_provider: Literal["local", "s3"] = "local"
    storage_local_root: str = "../storage"

    # ---- Provider selection ----
    ai_provider: Literal["anthropic", "openai", "gemini", "stub"] = "stub"
    research_provider: Literal["tavily", "brave", "serpapi", "stub"] = "stub"
    voice_provider: Literal["elevenlabs", "openai", "local", "stub"] = "stub"
    image_provider: Literal["openai", "stability", "replicate", "stub"] = "stub"
    video_clip_provider: Literal["replicate", "stub"] = "stub"
    stock_provider: Literal["pexels", "pixabay", "stub"] = "stub"
    youtube_provider: Literal["google", "stub"] = "stub"
    notifier_provider: Literal["twilio", "meta_cloud", "console", "stub"] = "console"

    # ---- AI keys ----
    anthropic_api_key: Optional[str] = None
    model: str = "claude-sonnet-4-5"
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    # ---- Research ----
    tavily_api_key: Optional[str] = None
    brave_api_key: Optional[str] = None
    serpapi_api_key: Optional[str] = None

    # ---- Voice ----
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None

    # ---- Visuals ----
    stability_api_key: Optional[str] = None
    replicate_api_token: Optional[str] = None
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None

    # ---- YouTube ----
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_oauth_redirect: Optional[str] = None
    youtube_default_privacy: Literal["private", "unlisted", "public"] = "private"
    youtube_default_category_id: str = "27"

    # ---- WhatsApp ----
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_from: Optional[str] = None
    whatsapp_to: Optional[str] = None
    twilio_status_callback: Optional[str] = None
    meta_waba_token: Optional[str] = None
    meta_phone_number_id: Optional[str] = None
    meta_verify_token: Optional[str] = None

    # ---- Storage (S3) ----
    s3_bucket: Optional[str] = None
    s3_region: Optional[str] = None
    s3_endpoint: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # ---- Automation / limits ----
    scheduler_enabled: bool = False
    jobs_async: bool = False  # True = enqueue pipeline runs to RQ; False = run inline
    max_concurrent_jobs: int = 1
    max_stage_retries: int = 3
    retry_backoff_base_sec: int = 10
    daily_video_limit: int = 3
    artifact_retention_days: int = 30
    yt_daily_quota_units: int = 10000

    # ---- Hardening ----
    rate_limit_enabled: bool = True
    rate_limit_login_per_min: int = 10
    rate_limit_write_per_min: int = 60
    web_dist: Optional[str] = None  # override the served dashboard build dir

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
