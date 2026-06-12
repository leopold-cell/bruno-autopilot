from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load a local .env if present, but do NOT override real environment variables
# (e.g. those injected by docker-compose env_file/environment) — those must win.
from dotenv import load_dotenv

load_dotenv(override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_nested_delimiter=None)

    # App
    app_name: str = "Bruno Autopilot"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://bruno:bruno@localhost:5432/bruno_autopilot"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic (Claude)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 8192

    # Supabase (Bruno project) — autopilot writes published posts here.
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # DataForSEO (real keyword volume + difficulty, USA). Optional — when unset,
    # keyword research falls back to Claude ideation.
    dataforseo_login: str = ""
    dataforseo_password: str = ""

    # MailerLite — weekly digest (best post of the week) to the email list.
    mailerlite_api_key: str = ""
    mailerlite_group_id: str = ""
    mailerlite_from_email: str = "hi@brunomind.com"
    mailerlite_from_name: str = "Bruno"
    weekly_digest_enabled: bool = True
    weekly_digest_day: str = "sun"  # cron day_of_week (mon..sun)
    weekly_digest_time: str = "09:00"  # HH:MM in publish_timezone

    # Brand / market
    brand_name: str = "Bruno"
    site_url: str = "https://brunomind.com"
    target_market: str = "US"
    # Themes the keyword researcher expands into problem-based queries.
    seed_themes: list[str] = [
        "anxiety",
        "overthinking",
        "low mood and depression",
        "sleep and insomnia",
        "stress and burnout",
        "panic attacks",
        "negative thinking and CBT",
    ]

    # Publishing cadence
    publish_time: str = "06:00"
    publish_timezone: str = "America/New_York"
    posts_per_run: int = 1
    min_queued_keywords: int = 10  # below this, the daily run tops up the queue first

    # Content guardrails
    min_body_words: int = 700
    require_crisis_disclaimer: bool = True
    crisis_line_us: str = "988 Suicide & Crisis Lifeline"

    # Google Search Console (later phase)
    google_service_account_json: str = ""
    gsc_site_url: str = ""

    # Metrics
    metrics_port: int = 9091


settings = Settings()
