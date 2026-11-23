"""Idempotent upserts and read queries for the kiosk UI."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from rmg_watcher.constants import DEFAULT_DEPARTURE_LIMIT
from rmg_watcher.domain.models import (
    DelayCategory,
    DelayEvent,
    Route,
    Stop,
    TripStatus,
)
from rmg_watcher.places import stop_name_key
from rmg_watcher.storage.db import Database
from rmg_watcher.transform.metrics import (
    MetricsSummary,
    TransferRisk,
    assess_transfer_risks,
    summarize_metrics,
)
from rmg_watcher.transform.validator import QuarantinedRecord


@dataclass(frozen=True, slots=True)
class DepartureView:
    """A departure row ready for the kiosk API."""

    trip_id: str
    route_id: str
    route_short_name: str
    stop_id: str
    stop_name: str
    scheduled_time: datetime
    expected_time: datetime | None
    delay_seconds: int | None
    delay_category: str
    status: str
    mode: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineRun:
    """A recorded pipeline execution."""

    run_id: str
    started_at: datetime
    finished_at: datetime | None
    raw_count: int
    valid_count: int
    deduplicated_count: int
    loaded_count: int
    quarantined_count: int
    status: str


class TransitRepository:
    """Persists dimensions and facts idempotently and serves read queries."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_stops(self, stops: Sequence[Stop]) -> int:
        timestamp = datetime.now(UTC).isoformat()
        rows = [
            (stop.stop_id, stop.name, stop.latitude, stop.longitude, timestamp) for stop in stops
        ]
        with self.database.session() as connection:
            connection.executemany(
                """
                INSERT INTO dim_stops (stop_id, name, latitude, longitude, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (stop_id) DO UPDATE SET
                    name = excluded.name,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def upsert_routes(self, routes: Sequence[Route]) -> int:
        timestamp = datetime.now(UTC).isoformat()
        rows = [
            (route.route_id, route.short_name, route.long_name, route.mode, timestamp)
            for route in routes
        ]
        with self.database.session() as connection:
            connection.executemany(
                """
                INSERT INTO dim_routes (route_id, short_name, long_name, mode, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (route_id) DO UPDATE SET
                    short_name = excluded.short_name,
                    long_name = excluded.long_name,
                    mode = excluded.mode,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def upsert_events(self, events: Sequence[DelayEvent]) -> int:
        rows = [
            (
                event.trip_id,
                event.route_id,
                event.stop_id,
                event.scheduled_time.isoformat(),
                event.expected_time.isoformat() if event.expected_time else None,
                event.delay_seconds,
                event.delay_category.value,
                event.status.value,
                event.observed_at.isoformat(),
            )
            for event in events
        ]
        with self.database.session() as connection:
            connection.executemany(
                """
                INSERT INTO fact_stop_events (
                    trip_id, route_id, stop_id, scheduled_time, expected_time,
                    delay_seconds, delay_category, status, observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (trip_id, stop_id) DO UPDATE SET
                    route_id = excluded.route_id,
                    scheduled_time = excluded.scheduled_time,
                    expected_time = excluded.expected_time,
                    delay_seconds = excluded.delay_seconds,
                    delay_category = excluded.delay_category,
                    status = excluded.status,
                    observed_at = excluded.observed_at
                """,
                rows,
            )
        return len(rows)

    def insert_quarantine(self, records: Sequence[QuarantinedRecord]) -> int:
        rows = [
            (
                record.batch_id,
                record.record_hash,
                record.reason,
                json.dumps(dict(record.payload), sort_keys=True, default=str),
                record.quarantined_at.isoformat(),
            )
            for record in records
        ]
        with self.database.session() as connection:
            connection.executemany(
                """
                INSERT INTO quarantine (
                    batch_id, record_hash, reason, payload, quarantined_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (batch_id, record_hash) DO NOTHING
                """,
                rows,
            )
        return len(rows)

    def start_run(self, run_id: str, started_at: datetime) -> None:
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs (run_id, started_at, status)
                VALUES (?, ?, 'running')
                ON CONFLICT (run_id) DO UPDATE SET
                    started_at = excluded.started_at,
                    finished_at = NULL,
                    status = 'running'
                """,
                (run_id, started_at.isoformat()),
            )

    def finish_run(
        self,
        run_id: str,
        *,
        finished_at: datetime,
        raw_count: int,
        valid_count: int,
        deduplicated_count: int,
        loaded_count: int,
        quarantined_count: int,
        status: str,
    ) -> None:
        with self.database.session() as connection:
            connection.execute(
                """
                UPDATE pipeline_runs
                SET finished_at = ?, raw_count = ?, valid_count = ?,
                    deduplicated_count = ?, loaded_count = ?,
                    quarantined_count = ?, status = ?
                WHERE run_id = ?
                """,
                (
                    finished_at.isoformat(),
                    raw_count,
                    valid_count,
                    deduplicated_count,
                    loaded_count,
                    quarantined_count,
                    status,
                    run_id,
                ),
            )

    def latest_run(self) -> PipelineRun | None:
        with self.database.session() as connection:
            row = connection.execute(
                """
                SELECT run_id, started_at, finished_at, raw_count, valid_count,
                       deduplicated_count, loaded_count, quarantined_count, status
                FROM pipeline_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return PipelineRun(
            run_id=row["run_id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=(
                datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
            ),
            raw_count=row["raw_count"],
            valid_count=row["valid_count"],
            deduplicated_count=row["deduplicated_count"],
            loaded_count=row["loaded_count"],
            quarantined_count=row["quarantined_count"],
            status=row["status"],
        )

    def list_stops(self) -> list[Stop]:
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT stop_id, name, latitude, longitude
                FROM dim_stops
                ORDER BY name
                """
            ).fetchall()
        stops = [
            Stop(
                stop_id=row["stop_id"],
                name=row["name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
            )
            for row in rows
        ]
        seen: set[str] = set()
        unique: list[Stop] = []
        for stop in stops:
            key = stop_name_key(stop.name)
            if key in seen:
                continue
            seen.add(key)
            unique.append(stop)
        return unique

    def get_stop(self, stop_id: str) -> Stop | None:
        with self.database.session() as connection:
            row = connection.execute(
                """
                SELECT stop_id, name, latitude, longitude
                FROM dim_stops
                WHERE stop_id = ?
                """,
                (stop_id,),
            ).fetchone()
        if row is None:
            return None
        return Stop(
            stop_id=row["stop_id"],
            name=row["name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
        )

    def list_departures(
        self,
        stop_id: str,
        *,
        limit: int = DEFAULT_DEPARTURE_LIMIT,
    ) -> list[DepartureView]:
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT f.trip_id, f.route_id, r.short_name AS route_short_name,
                       r.mode AS mode, f.stop_id, s.name AS stop_name,
                       f.scheduled_time, f.expected_time, f.delay_seconds,
                       f.delay_category, f.status
                FROM fact_stop_events AS f
                JOIN dim_routes AS r ON r.route_id = f.route_id
                JOIN dim_stops AS s ON s.stop_id = f.stop_id
                WHERE f.stop_id = ?
                ORDER BY f.scheduled_time
                LIMIT ?
                """,
                (stop_id, limit),
            ).fetchall()
        return [
            DepartureView(
                trip_id=row["trip_id"],
                route_id=row["route_id"],
                route_short_name=row["route_short_name"],
                stop_id=row["stop_id"],
                stop_name=row["stop_name"],
                scheduled_time=datetime.fromisoformat(row["scheduled_time"]),
                expected_time=(
                    datetime.fromisoformat(row["expected_time"]) if row["expected_time"] else None
                ),
                delay_seconds=row["delay_seconds"],
                delay_category=row["delay_category"],
                status=row["status"],
                mode=row["mode"],
            )
            for row in rows
        ]

    def list_events(self, *, limit: int = 5_000) -> list[DelayEvent]:
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT trip_id, route_id, stop_id, scheduled_time, expected_time,
                       delay_seconds, delay_category, status, observed_at
                FROM fact_stop_events
                ORDER BY scheduled_time DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            DelayEvent(
                trip_id=row["trip_id"],
                route_id=row["route_id"],
                stop_id=row["stop_id"],
                scheduled_time=datetime.fromisoformat(row["scheduled_time"]),
                expected_time=(
                    datetime.fromisoformat(row["expected_time"]) if row["expected_time"] else None
                ),
                delay_seconds=row["delay_seconds"],
                delay_category=DelayCategory(row["delay_category"]),
                status=TripStatus(row["status"]),
                observed_at=datetime.fromisoformat(row["observed_at"]),
            )
            for row in rows
        ]

    def _stop_names(self) -> dict[str, str]:
        with self.database.session() as connection:
            rows = connection.execute("SELECT stop_id, name FROM dim_stops").fetchall()
        return {str(row["stop_id"]): str(row["name"]) for row in rows if row["name"]}

    def _route_names(self) -> dict[str, str]:
        with self.database.session() as connection:
            rows = connection.execute("SELECT route_id, short_name FROM dim_routes").fetchall()
        return {str(row["route_id"]): str(row["short_name"]) for row in rows if row["short_name"]}

    def metrics_summary(self, *, limit: int = 5_000) -> MetricsSummary:
        summary = summarize_metrics(self.list_events(limit=limit))
        return replace(summary, route_names=self._route_names())

    def transfer_risks(self, *, limit: int = 5_000) -> list[TransferRisk]:
        names = self._route_names()
        stop_names = self._stop_names()
        return [
            replace(
                risk,
                inbound_route_name=names.get(risk.inbound_route_id),
                outbound_route_name=names.get(risk.outbound_route_id),
                stop_name=stop_names.get(risk.stop_id),
            )
            for risk in assess_transfer_risks(self.list_events(limit=limit))
        ]

    def metrics_and_risks(
        self,
        *,
        limit: int = 5_000,
    ) -> tuple[MetricsSummary, list[TransferRisk]]:
        """Compute metrics and transfer risks from one event query."""
        events = self.list_events(limit=limit)
        route_names = self._route_names()
        stop_names = self._stop_names()

        summary = replace(summarize_metrics(events), route_names=route_names)
        risks = [
            replace(
                risk,
                inbound_route_name=route_names.get(risk.inbound_route_id),
                outbound_route_name=route_names.get(risk.outbound_route_id),
                stop_name=stop_names.get(risk.stop_id),
            )
            for risk in assess_transfer_risks(events)
        ]
        return summary, risks

    def count_events(self) -> int:
        with self.database.session() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM fact_stop_events").fetchone()[0])

    def count_stops(self) -> int:
        with self.database.session() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM dim_stops").fetchone()[0])

    def count_quarantine(self) -> int:
        with self.database.session() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0])

    def count_null_violations(self) -> int:
        with self.database.session() as connection:
            return int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM fact_stop_events
                    WHERE trip_id IS NULL OR trip_id = ''
                       OR route_id IS NULL OR route_id = ''
                       OR stop_id IS NULL OR stop_id = ''
                       OR scheduled_time IS NULL OR scheduled_time = ''
                       OR delay_category IS NULL OR delay_category = ''
                       OR status IS NULL OR status = ''
                    """
                ).fetchone()[0]
            )

    def foreign_key_violations(self) -> int:
        with self.database.session() as connection:
            rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        return len(rows)
