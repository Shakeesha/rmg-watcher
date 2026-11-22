"""Verifies repeated pipeline runs produce no duplicate rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from rmg_watcher.domain.models import (
    DelayCategory,
    DelayEvent,
    Route,
    Stop,
    TripStatus,
)
from rmg_watcher.quality.checks import run_quality_checks
from rmg_watcher.storage.db import Database
from rmg_watcher.storage.repository import TransitRepository
from rmg_watcher.transform.validator import QuarantinedRecord

EXPECTED_TABLES = {
    "dim_routes",
    "dim_stops",
    "fact_stop_events",
    "pipeline_runs",
    "quarantine",
}

SCHEDULED = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
OBSERVED = datetime(2026, 11, 21, 8, 1, tzinfo=UTC)


def _repository(tmp_path: Path) -> TransitRepository:
    database = Database(tmp_path / "transit.db")
    database.initialize()
    return TransitRepository(database)


def _event(
    *,
    delay_seconds: int = 240,
    delay_category: DelayCategory = DelayCategory.MINOR,
) -> DelayEvent:
    return DelayEvent(
        trip_id="trip-1",
        route_id="route-4",
        stop_id="luisenplatz",
        scheduled_time=SCHEDULED,
        expected_time=SCHEDULED + timedelta(seconds=delay_seconds),
        delay_seconds=delay_seconds,
        delay_category=delay_category,
        status=TripStatus.DELAYED,
        observed_at=OBSERVED,
    )


def _seed(repository: TransitRepository) -> None:
    repository.upsert_stops([Stop("luisenplatz", "Darmstadt Luisenplatz")])
    repository.upsert_routes([Route("route-4", "4", mode="tram")])


def test_initialize_creates_schema(tmp_path: Path) -> None:
    database = Database(tmp_path / "transit.db")

    database.initialize()

    with database.session() as connection:
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert tables >= EXPECTED_TABLES


def test_initialize_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "transit.db")

    database.initialize()
    database.initialize()

    with database.session() as connection:
        count = connection.execute("SELECT COUNT(*) FROM dim_stops").fetchone()[0]
    assert count == 0


def test_wal_mode_and_foreign_keys_are_enabled(tmp_path: Path) -> None:
    database = Database(tmp_path / "transit.db")
    database.initialize()

    with database.session() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert journal_mode == "wal"
    assert foreign_keys == 1


def test_event_upserts_are_idempotent(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _seed(repository)

    assert repository.upsert_events([_event()]) == 1
    assert repository.upsert_events([_event()]) == 1

    assert repository.count_events() == 1
    assert repository.count_stops() == 1


def test_event_upsert_updates_existing_row(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _seed(repository)

    repository.upsert_events([_event(delay_seconds=240)])
    repository.upsert_events([_event(delay_seconds=600, delay_category=DelayCategory.MAJOR)])

    departures = repository.list_departures("luisenplatz")
    assert len(departures) == 1
    assert departures[0].delay_seconds == 600
    assert departures[0].delay_category == "major"


def test_quarantine_records_are_appended(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    record = QuarantinedRecord(
        batch_id="batch-1",
        record_hash="a" * 64,
        reason="tripId: Field required",
        payload={"stopId": "luisenplatz"},
        quarantined_at=OBSERVED,
    )

    repository.insert_quarantine([record])

    assert repository.count_quarantine() == 1


def test_quality_checks_reconcile_counts(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _seed(repository)
    repository.upsert_events([_event()])

    report = run_quality_checks(
        raw_count=3,
        valid_count=2,
        deduplicated_count=1,
        loaded_count=1,
        quarantined_count=1,
        repository=repository,
    )

    assert report.ok
    assert report.errors == []


def test_quality_checks_flag_mismatched_counts(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _seed(repository)
    repository.upsert_events([_event()])

    report = run_quality_checks(
        raw_count=5,
        valid_count=2,
        deduplicated_count=1,
        loaded_count=1,
        quarantined_count=1,
        repository=repository,
    )

    assert not report.ok
    assert any("raw count mismatch" in error for error in report.errors)
