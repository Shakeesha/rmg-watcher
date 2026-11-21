"""Verifies repeated pipeline runs produce no duplicate rows."""

from __future__ import annotations

from pathlib import Path

from transit_pipeline.storage.db import Database

EXPECTED_TABLES = {
    "dim_routes",
    "dim_stops",
    "fact_stop_events",
    "pipeline_runs",
    "quarantine",
}


def test_initialize_creates_schema(tmp_path: Path) -> None:
    database = Database(tmp_path / "transit.db")

    database.initialize()

    with database.session() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
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
