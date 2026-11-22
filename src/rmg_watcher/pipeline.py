"""Pipeline orchestration: ingest, transform, load, and quality gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from rmg_watcher.config import Settings
from rmg_watcher.domain.models import DelayEvent, Route, Stop
from rmg_watcher.ingestion.fetcher import TransitFetcher, create_fetcher
from rmg_watcher.ingestion.raw_store import RawStore
from rmg_watcher.quality.checks import QualityReport, run_quality_checks
from rmg_watcher.storage.db import Database
from rmg_watcher.storage.repository import TransitRepository
from rmg_watcher.transform.deduplicator import deduplicate_departures
from rmg_watcher.transform.enricher import (
    enrich_departures,
    routes_from_departures,
    stops_from_payload,
)
from rmg_watcher.transform.validator import (
    QuarantinedRecord,
    ValidDeparture,
    validate_departures,
)


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Raw payloads captured for a single batch."""

    batch_id: str
    observed_at: datetime
    stops: list[Stop]
    raw_records: list[dict[str, Any]]
    snapshot_path: Path


@dataclass(frozen=True, slots=True)
class TransformResult:
    """Validated, deduplicated, and enriched records for a batch."""

    batch_id: str
    observed_at: datetime
    valid: list[ValidDeparture]
    unique: list[ValidDeparture]
    duplicates: int
    events: list[DelayEvent]
    routes: list[Route]
    quarantined: list[QuarantinedRecord]


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Counts and quality outcome of a full pipeline run."""

    run_id: str
    raw_count: int
    valid_count: int
    deduplicated_count: int
    loaded_count: int
    quarantined_count: int
    raw_snapshot: Path
    quality: QualityReport


def ingest(
    settings: Settings,
    *,
    fetcher: TransitFetcher | None = None,
    batch_id: str | None = None,
    now: datetime | None = None,
) -> IngestResult:
    """Fetch raw stops and departures and persist an immutable snapshot."""
    batch = batch_id or uuid4().hex
    observed_at = now or datetime.now(UTC)
    client = fetcher or create_fetcher(settings)

    try:
        stops = stops_from_payload(client.fetch_stops())
        raw_records: list[dict[str, Any]] = []
        for stop in stops:
            raw_records.extend(client.fetch_departures(stop.stop_id))
    finally:
        if fetcher is None:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    snapshot = RawStore(settings.raw_store_path).write_batch(
        raw_records,
        source="departures",
        batch_id=batch,
        fetched_at=observed_at,
    )
    return IngestResult(
        batch_id=batch,
        observed_at=observed_at,
        stops=stops,
        raw_records=raw_records,
        snapshot_path=snapshot,
    )


def transform(ingested: IngestResult) -> TransformResult:
    """Validate, deduplicate, and enrich an ingested batch."""
    validation = validate_departures(
        ingested.raw_records,
        batch_id=ingested.batch_id,
        quarantined_at=ingested.observed_at,
    )
    unique, duplicates = deduplicate_departures(validation.valid)
    events = enrich_departures(unique, observed_at=ingested.observed_at)
    return TransformResult(
        batch_id=ingested.batch_id,
        observed_at=ingested.observed_at,
        valid=validation.valid,
        unique=unique,
        duplicates=duplicates,
        events=events,
        routes=routes_from_departures(unique),
        quarantined=validation.quarantined,
    )


def load(
    settings: Settings,
    ingested: IngestResult,
    transformed: TransformResult,
) -> PipelineResult:
    """Upsert a transformed batch and run the quality gates."""
    database = Database(settings.database_path)
    database.initialize()
    repository = TransitRepository(database)
    repository.start_run(ingested.batch_id, ingested.observed_at)

    raw_count = len(ingested.raw_records)
    valid_count = len(transformed.valid)
    loaded_count = len(transformed.events)
    quarantined_count = len(transformed.quarantined)

    try:
        repository.upsert_stops(ingested.stops)
        repository.upsert_routes(transformed.routes)
        repository.upsert_events(transformed.events)
        repository.insert_quarantine(transformed.quarantined)

        quality = run_quality_checks(
            raw_count=raw_count,
            valid_count=valid_count,
            deduplicated_count=transformed.duplicates,
            loaded_count=loaded_count,
            quarantined_count=quarantined_count,
            repository=repository,
        )
    except Exception:
        # Any failure must mark the run as failed before re-raising.
        repository.finish_run(
            ingested.batch_id,
            finished_at=datetime.now(UTC),
            raw_count=raw_count,
            valid_count=valid_count,
            deduplicated_count=transformed.duplicates,
            loaded_count=loaded_count,
            quarantined_count=quarantined_count,
            status="failed",
        )
        raise

    repository.finish_run(
        ingested.batch_id,
        finished_at=datetime.now(UTC),
        raw_count=raw_count,
        valid_count=valid_count,
        deduplicated_count=transformed.duplicates,
        loaded_count=loaded_count,
        quarantined_count=quarantined_count,
        status="ok" if quality.ok else "quality_failed",
    )

    return PipelineResult(
        run_id=ingested.batch_id,
        raw_count=raw_count,
        valid_count=valid_count,
        deduplicated_count=transformed.duplicates,
        loaded_count=loaded_count,
        quarantined_count=quarantined_count,
        raw_snapshot=ingested.snapshot_path,
        quality=quality,
    )


def run_pipeline(
    settings: Settings,
    *,
    fetcher: TransitFetcher | None = None,
    batch_id: str | None = None,
    now: datetime | None = None,
) -> PipelineResult:
    """Run ingest, transform, load, and quality checks in sequence."""
    ingested = ingest(settings, fetcher=fetcher, batch_id=batch_id, now=now)
    transformed = transform(ingested)
    return load(settings, ingested, transformed)
