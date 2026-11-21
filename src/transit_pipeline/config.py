"""Environment configuration and automatic mock-mode switching."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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

    transit_api_base_url: str = Field(
        default="https://example.invalid/api",
        validation_alias="TRANSIT_API_BASE_URL",
    )
    transit_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="TRANSIT_API_KEY",
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
