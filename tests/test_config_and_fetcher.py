"""Tests for automatic mock mode under pytest and client behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from rmg_watcher.config import (
    PROJECT_ROOT,
    Settings,
    get_settings,
    is_pytest_running,
)
from rmg_watcher.ingestion.fetcher import MockTransitClient, create_fetcher


def test_env_example_documents_every_setting() -> None:
    example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    documented = {
        line.split("=", 1)[0].strip()
        for line in example.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    aliases = {str(field.validation_alias) for field in Settings.model_fields.values()}

    assert aliases <= documented


def test_pytest_is_detected() -> None:
    assert is_pytest_running() is True


def test_mock_mode_is_forced_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_MOCK_MODE", "false")
    assert Settings(_env_file=None).mock_mode is True


def test_explicit_mock_mode_outside_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("PIPELINE_MOCK_MODE", "true")
    assert Settings(_env_file=None).mock_mode is True


def test_live_mode_outside_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PIPELINE_MOCK_MODE", raising=False)
    assert Settings(_env_file=None).mock_mode is False


def test_defaults_target_project_directories(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DATABASE_PATH",
        "RAW_STORE_PATH",
        "QUARANTINE_PATH",
        "FRONTEND_DIST_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_path == PROJECT_ROOT / "data" / "transit.db"
    assert settings.raw_store_path == PROJECT_ROOT / "data" / "raw"
    assert settings.quarantine_path == PROJECT_ROOT / "data" / "quarantine"
    assert settings.frontend_dist_path == PROJECT_ROOT / "frontend" / "dist"


def test_environment_paths_are_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", "custom/transit.db")
    assert Settings(_env_file=None).database_path == Path("custom/transit.db")


def test_blank_api_key_is_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSIT_API_KEY", "   ")
    assert Settings(_env_file=None).transit_api_key is None


def test_api_key_is_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSIT_API_KEY", "secret-key")
    settings = Settings(_env_file=None)

    assert settings.transit_api_key is not None
    assert settings.transit_api_key.get_secret_value() == "secret-key"
    assert "secret-key" not in repr(settings)


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()


def test_factory_returns_mock_client_in_mock_mode(settings: Settings) -> None:
    assert isinstance(create_fetcher(settings), MockTransitClient)


def test_mock_fetcher_returns_stop_metadata(mock_fetcher: MockTransitClient) -> None:
    stops = mock_fetcher.fetch_stops()

    assert {stop["stopId"] for stop in stops} == {"luisenplatz", "hbf"}


def test_mock_fetcher_filters_departures_by_stop(
    mock_fetcher: MockTransitClient,
) -> None:
    departures = mock_fetcher.fetch_departures("luisenplatz")

    assert departures
    assert all(record["stopId"] == "luisenplatz" for record in departures)


def test_fixture_covers_duplicates_and_malformed_records(
    mock_fetcher: MockTransitClient,
) -> None:
    departures = mock_fetcher.fetch_departures("luisenplatz")
    trip_ids = [record.get("tripId") for record in departures]

    assert None in trip_ids
    assert len(trip_ids) != len(set(trip_ids))
