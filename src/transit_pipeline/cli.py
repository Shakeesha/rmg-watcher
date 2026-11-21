"""Command-line interface: ingest, transform, run, quality-check, serve."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict

from transit_pipeline.config import get_settings
from transit_pipeline.pipeline import ingest, run_pipeline, transform
from transit_pipeline.quality.checks import run_quality_checks
from transit_pipeline.storage.db import Database
from transit_pipeline.storage.repository import TransitRepository


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transit-pipeline",
        description="Transit delay telemetry pipeline",
    )
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser("ingest", help="fetch and store a raw batch")
    ingest_parser.add_argument("--batch-id", default=None)

    transform_parser = subparsers.add_parser(
        "transform",
        help="fetch, validate, deduplicate, and enrich without loading",
    )
    transform_parser.add_argument("--batch-id", default=None)

    run_parser = subparsers.add_parser("run", help="run the full pipeline")
    run_parser.add_argument("--batch-id", default=None)

    subparsers.add_parser("quality-check", help="check the latest run and database")

    return parser


def _quality_check() -> int:
    settings = get_settings()
    database = Database(settings.database_path)
    database.initialize()
    repository = TransitRepository(database)
    latest = repository.latest_run()
    if latest is None:
        print("No pipeline runs recorded.")
        return 1

    report = run_quality_checks(
        raw_count=latest.raw_count,
        valid_count=latest.valid_count,
        deduplicated_count=latest.deduplicated_count,
        loaded_count=latest.loaded_count,
        quarantined_count=latest.quarantined_count,
        repository=repository,
    )
    print(json.dumps(asdict(report), indent=2))
    return 0 if report.ok else 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1

    settings = get_settings()

    if args.command == "ingest":
        ingested = ingest(settings, batch_id=args.batch_id)
        print(
            json.dumps(
                {
                    "batch_id": ingested.batch_id,
                    "stop_count": len(ingested.stops),
                    "raw_count": len(ingested.raw_records),
                    "snapshot": str(ingested.snapshot_path),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "transform":
        ingested = ingest(settings, batch_id=args.batch_id)
        transformed = transform(ingested)
        print(
            json.dumps(
                {
                    "batch_id": transformed.batch_id,
                    "valid_count": len(transformed.valid),
                    "unique_count": len(transformed.unique),
                    "duplicates": transformed.duplicates,
                    "event_count": len(transformed.events),
                    "quarantined_count": len(transformed.quarantined),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "run":
        result = run_pipeline(settings, batch_id=args.batch_id)
        print(json.dumps(asdict(result), default=str, indent=2))
        return 0 if result.quality.ok else 2

    if args.command == "quality-check":
        return _quality_check()

    parser.print_help()
    return 1
