"""Environment-driven settings. Model names and all limits are configurable, never hardcoded elsewhere."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PharmaSource"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://pharmasource:pharmasource@localhost:5432/pharmasource"
    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False

    # Vision providers (keys stay server-side)
    openai_api_key: str = ""
    openai_vision_model: str = ""
    gemini_api_key: str = ""
    gemini_vision_model: str = ""
    provider_timeout_seconds: float = 60.0

    # Uploads
    max_upload_mb: float = 8.0
    max_image_pixels: int = 40_000_000
    image_max_side: int = 1600

    # Web discovery / extraction
    tavily_api_key: str = ""
    tavily_max_results: int = 8
    page_fetch_timeout_seconds: float = 10.0
    page_fetch_max_bytes: int = 1_500_000
    respect_robots: bool = True
    http_user_agent: str = "PharmaSourceBot/0.1 (+price-comparison; contact: set-in-env)"

    # Currency
    fx_provider: str = "none"  # none | static | frankfurter
    fx_static_rates: str = ""  # "USD>INR=83.10,EUR>INR=90.2"
    india_currency: str = "INR"
    global_currency: str = "USD"

    # Search workflow
    demo_mode: bool = False
    source_timeout_seconds: float = 20.0
    source_max_retries: int = 1
    source_max_concurrency: int = 4
    search_timeout_seconds: float = 120.0
    max_concurrent_searches_per_session: int = 3
    offer_max_age_hours: float = 24.0
    rate_limit_per_minute: int = 30
    identify_rate_limit_per_minute: int = 10

    reference_data_csv: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


Settings.model_rebuild()


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings", "Field"]
