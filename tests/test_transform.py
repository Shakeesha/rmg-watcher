"""Tests for validation, quarantine routing, deduplication, and metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from rmg_watcher.domain.models import DelayCategory, TripStatus
from rmg_watcher.ingestion.fetcher import MockTransitClient
from rmg_watcher.transform.deduplicator import deduplicate_departures
from rmg_watcher.transform.enricher import (
    categorize_delay,
    compute_delay_seconds,
    enrich_departures,
)
from rmg_watcher.transform.metrics import (
    assess_transfer_risks,
    percentile,
    punctuality_rate,
    summarize_metrics,
)
from rmg_watcher.transform.validator import hash_record, validate_departures

BATCH_ID = "batch-1"
QUARANTINED_AT = datetime(2026, 11, 21, 8, 30, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)


@pytest.fixture
def raw_luisenplatz(mock_fetcher: MockTransitClient) -> list[dict[str, Any]]:
    return mock_fetcher.fetch_departures("luisenplatz")


def test_validation_splits_valid_and_quarantined(
    raw_luisenplatz: list[dict[str, Any]],
) -> None:
    result = validate_departures(
        raw_luisenplatz,
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    )

    assert len(result.valid) == 5
    assert len(result.quarantined) == 2
    reasons = " ".join(record.reason for record in result.quarantined)
    assert "tripId" in reasons
    assert "scheduledTime" in reasons


def test_quarantine_records_are_hashed_and_preserved(
    raw_luisenplatz: list[dict[str, Any]],
) -> None:
    result = validate_departures(
        raw_luisenplatz,
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    )

    record = result.quarantined[0]
    assert len(record.record_hash) == 64
    assert record.payload in raw_luisenplatz
    assert record.batch_id == BATCH_ID
    assert record.quarantined_at == QUARANTINED_AT


def test_hash_is_stable_for_reordered_keys() -> None:
    assert hash_record({"a": 1, "b": 2}) == hash_record({"b": 2, "a": 1})


def test_duplicates_keep_the_latest_update(
    raw_luisenplatz: list[dict[str, Any]],
) -> None:
    valid = validate_departures(
        raw_luisenplatz,
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    ).valid

    unique, duplicates = deduplicate_departures(valid)

    assert duplicates == 1
    assert len(unique) == 4
    trip = next(record for record in unique if record.trip_id == "trip-1001")
    assert trip.expected_time is not None
    assert trip.expected_time.minute == 4


def test_enrichment_computes_delay_and_category(
    raw_luisenplatz: list[dict[str, Any]],
) -> None:
    valid = validate_departures(
        raw_luisenplatz,
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    ).valid
    unique, _ = deduplicate_departures(valid)

    events = enrich_departures(unique, observed_at=OBSERVED_AT)
    by_trip = {event.trip_id: event for event in events}

    assert by_trip["trip-1001"].delay_seconds == 240
    assert by_trip["trip-1001"].delay_category is DelayCategory.MINOR
    assert by_trip["trip-1002"].delay_category is DelayCategory.ON_TIME
    assert by_trip["trip-1003"].delay_seconds is None
    assert by_trip["trip-1003"].delay_category is DelayCategory.CANCELLED
    assert by_trip["trip-1004"].delay_category is DelayCategory.MAJOR
    assert all(event.observed_at == OBSERVED_AT for event in events)


@pytest.mark.parametrize(
    ("delay", "expected"),
    [
        (None, DelayCategory.ON_TIME),
        (-120, DelayCategory.ON_TIME),
        (60, DelayCategory.ON_TIME),
        (61, DelayCategory.MINOR),
        (300, DelayCategory.MINOR),
        (301, DelayCategory.MAJOR),
        (900, DelayCategory.MAJOR),
        (901, DelayCategory.SEVERE),
    ],
)
def test_delay_categories(delay: int | None, expected: DelayCategory) -> None:
    assert categorize_delay(delay, TripStatus.DELAYED) is expected


def test_compute_delay_seconds() -> None:
    scheduled = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)

    assert (
        compute_delay_seconds(
            scheduled,
            scheduled + timedelta(seconds=90),
            TripStatus.DELAYED,
        )
        == 90
    )
    assert compute_delay_seconds(scheduled, None, TripStatus.DELAYED) is None
    assert compute_delay_seconds(scheduled, None, TripStatus.CANCELLED) is None


def test_metrics_summary_for_a_stop(mock_fetcher: MockTransitClient) -> None:
    raw = mock_fetcher.fetch_departures("hbf")
    valid = validate_departures(
        raw,
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    ).valid
    events = enrich_departures(valid, observed_at=OBSERVED_AT)

    summary = summarize_metrics(events)

    assert summary.total_events == 3
    assert summary.punctuality_rate == pytest.approx(2 / 3)
    assert summary.median_delay_seconds == 0
    assert summary.p95_delay_seconds == pytest.approx(1080)
    assert summary.top_delayed_routes[0] == ("route-H", 1200)


def test_punctuality_counts_cancellations_as_failures(
    raw_luisenplatz: list[dict[str, Any]],
) -> None:
    valid = validate_departures(
        raw_luisenplatz,
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    ).valid
    unique, _ = deduplicate_departures(valid)
    events = enrich_departures(unique, observed_at=OBSERVED_AT)

    assert punctuality_rate(events) == pytest.approx(0.5)


def test_percentile_handles_empty_and_single_values() -> None:
    assert percentile([], 50) is None
    assert percentile([42.0], 95) == 42.0


def test_transfer_risks_flag_negative_slack(
    raw_luisenplatz: list[dict[str, Any]],
) -> None:
    valid = validate_departures(
        raw_luisenplatz,
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    ).valid
    unique, _ = deduplicate_departures(valid)
    events = enrich_departures(unique, observed_at=OBSERVED_AT)

    risks = assess_transfer_risks(events)

    assert risks
    assert risks[0].stop_id == "luisenplatz"
    assert risks[0].inbound_route_id == "route-4"
    assert risks[0].outbound_route_id == "route-H"
    assert risks[0].projected_slack_seconds == -120
    assert risks[0].at_risk is True


def test_implausible_expected_time_is_quarantined() -> None:
    record = {
        "tripId": "trip-9000",
        "routeId": "route-4",
        "stopId": "hbf",
        "scheduledTime": "2026-11-21T08:00:00+01:00",
        "expectedTime": "2026-11-23T08:00:00+01:00",
        "status": "delayed",
    }

    result = validate_departures(
        [record],
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    )

    assert not result.valid
    assert "implausibly later" in result.quarantined[0].reason


def test_naive_timestamps_are_treated_as_utc() -> None:
    record = {
        "tripId": "trip-9001",
        "routeId": "route-4",
        "stopId": "hbf",
        "scheduledTime": "2026-11-21T08:00:00",
        "expectedTime": "2026-11-21T08:01:00",
        "status": "delayed",
    }

    result = validate_departures(
        [record],
        batch_id=BATCH_ID,
        quarantined_at=QUARANTINED_AT,
    )

    assert result.valid[0].scheduled_time.tzinfo is UTC
