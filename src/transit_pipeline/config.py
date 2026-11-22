"""Environment configuration and automatic mock-mode switching."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCH_STOPS = ()


def is_pytest_running() -> bool:
    """Return True while a pytest test is executing."""
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    mock_mode: bool = Field(default=False, validation_alias="PIPELINE_MOCK_MODE")
    database_path: Path = Field(
        default=PROJECT_ROOT / "data" / "transit.db",
        validation_alias="DATABASE_PATH",
    )
    raw_store_path: Path = Field(
        default=PROJECT_ROOT / "data" / "raw",
        validation_alias="RAW_STORE_PATH",
    )
    quarantine_path: Path = Field(
        default=PROJECT_ROOT / "data" / "quarantine",
        validation_alias="QUARANTINE_PATH",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    transit_provider: Literal["transitous", "generic"] = Field(
        default="transitous",
        validation_alias="TRANSIT_PROVIDER",
    )
    transit_api_base_url: str = Field(
        default="https://example.invalid/api",
        validation_alias="TRANSIT_API_BASE_URL",
    )
    transit_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="TRANSIT_API_KEY",
    )

    transitous_base_url: str = Field(
        default="https://api.transitous.org/api",
        validation_alias="TRANSITOUS_BASE_URL",
    )
    transitous_contact: str | None = Field(
        default=None,
        validation_alias="TRANSIT_CONTACT",
    )
    transitous_area_min: str = Field(
        default="49.80,9.00",
        validation_alias="TRANSITOUS_AREA_MIN",
    )
    transitous_area_max: str = Field(
        default="50.02,8.55",
        validation_alias="TRANSITOUS_AREA_MAX",
    )
    transitous_watch_stops: Annotated[tuple[str, ...], NoDecode] = Field(
        default=DEFAULT_WATCH_STOPS,
        validation_alias="TRANSITOUS_WATCH_STOPS",
    )
    transitous_departure_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        validation_alias="TRANSITOUS_DEPARTURE_LIMIT",
    )
    transitous_min_refresh_seconds: int = Field(
        default=600,
        ge=60,
        validation_alias="TRANSITOUS_MIN_REFRESH_SECONDS",
    )
    transitous_plan_limit_per_day: int = Field(
        default=30,
        ge=1,
        le=200,
        validation_alias="TRANSITOUS_PLAN_LIMIT_PER_DAY",
    )
    transitous_plan_cache_minutes: int = Field(
        default=30,
        ge=1,
        le=240,
        validation_alias="TRANSITOUS_PLAN_CACHE_MINUTES",
    )
    transitous_nearby_radius_m: int = Field(
        default=1000,
        ge=50,
        le=5000,
        validation_alias="TRANSITOUS_NEARBY_RADIUS_M",
    )
    transitous_nearby_limit: int = Field(
        default=3,
        ge=1,
        le=20,
        validation_alias="TRANSITOUS_NEARBY_LIMIT",
    )
    transitous_home_lat: float = Field(
        default=49.872881,
        validation_alias="TRANSITOUS_HOME_LAT",
    )
    transitous_home_lon: float = Field(
        default=8.651252,
        validation_alias="TRANSITOUS_HOME_LON",
    )
    transitous_suggested_radius_m: int = Field(
        default=1500,
        ge=100,
        le=10000,
        validation_alias="TRANSITOUS_SUGGESTED_RADIUS_M",
    )
    transitous_suggested_limit: int = Field(
        default=3,
        ge=1,
        le=20,
        validation_alias="TRANSITOUS_SUGGESTED_LIMIT",
    )
    transitous_alert_stops: int = Field(
        default=3,
        ge=1,
        le=10,
        validation_alias="TRANSITOUS_ALERT_STOPS",
    )
    transitous_geocode_limit: int = Field(
        default=6,
        ge=1,
        le=10,
        validation_alias="TRANSITOUS_GEOCODE_LIMIT",
    )
    german_stops_path: Path = Field(
        default=PROJECT_ROOT / "data" / "german-stops.json",
        validation_alias="GERMAN_STOPS_PATH",
    )
    transitous_cache_path: Path = Field(
        default=PROJECT_ROOT / "data" / "transitous",
        validation_alias="TRANSITOUS_CACHE_PATH",
    )

    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    frontend_dist_path: Path = Field(
        default=PROJECT_ROOT / "frontend" / "dist",
        validation_alias="FRONTEND_DIST_PATH",
    )

    @field_validator("transit_api_key", mode="before")
    @classmethod
    def _blank_api_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("transitous_watch_stops", mode="before")
    @classmethod
    def _split_watch_stops(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @model_validator(mode="after")
    def _force_mock_mode_under_pytest(self) -> Settings:
        """Keep tests away from the live API regardless of configuration."""
        if is_pytest_running():
            self.mock_mode = True
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
