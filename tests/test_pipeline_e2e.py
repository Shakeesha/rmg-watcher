"""End-to-end pipeline run in mock mode."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rmg_watcher.cli import main
from rmg_watcher.config import Settings, get_settings
from rmg_watcher.pipeline import run_pipeline
from rmg_watcher.storage.db import Database
from rmg_watcher.storage.repository import TransitRepository

BATCH_ID = "batch-e2e"
NOW = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)


def _repository(settings: Settings) -> TransitRepository:
    return TransitRepository(Database(settings.database_path))


def test_pipeline_runs_in_mock_mode(settings: Settings) -> None:
    result = run_pipeline(settings, batch_id=BATCH_ID, now=NOW)

    assert result.raw_count == 10
    assert result.valid_count == 8
    assert result.deduplicated_count == 1
    assert result.loaded_count == 7
    assert result.quarantined_count == 2
    assert result.quality.ok
    assert result.raw_snapshot.exists()

    repository = _repository(settings)
    assert repository.count_stops() == 2
    assert repository.count_events() == 7
    assert repository.count_quarantine() == 2
    assert len(repository.list_departures("luisenplatz")) == 4

    latest = repository.latest_run()
    assert latest is not None
    assert latest.status == "ok"
    assert latest.raw_count == 10


def test_repeated_runs_do_not_duplicate_facts(settings: Settings) -> None:
    run_pipeline(settings, batch_id="run-1", now=NOW)
    run_pipeline(settings, batch_id="run-2", now=NOW)

    repository = _repository(settings)

    assert repository.count_events() == 7
    assert repository.count_stops() == 2


def test_pipeline_exposes_metrics_and_transfer_risks(settings: Settings) -> None:
    run_pipeline(settings, batch_id=BATCH_ID, now=NOW)
    repository = _repository(settings)

    summary = repository.metrics_summary()
    risks = repository.transfer_risks()

    assert summary.total_events == 7
    assert summary.top_delayed_routes[0] == ("route-H", 1200)
    assert risks
    assert risks[0].at_risk is True


def test_cli_run_uses_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setenv("RAW_STORE_PATH", str(tmp_path / "raw"))
    monkeypatch.setenv("QUARANTINE_PATH", str(tmp_path / "quarantine"))
    monkeypatch.setenv("PIPELINE_MOCK_MODE", "true")
    get_settings.cache_clear()

    try:
        exit_code = main(["run"])
    finally:
        get_settings.cache_clear()

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["loaded_count"] == 7
