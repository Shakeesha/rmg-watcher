"""Stop and route metadata joins, delay calculation, and status classification."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from rmg_watcher.domain.models import DelayCategory, DelayEvent, Route, Stop, TripStatus
from rmg_watcher.transform.validator import ValidDeparture

ON_TIME_THRESHOLD_SECONDS = 60
MINOR_THRESHOLD_SECONDS = 300
MAJOR_THRESHOLD_SECONDS = 900


def compute_delay_seconds(
    scheduled: datetime,
    expected: datetime | None,
    status: TripStatus,
) -> int | None:
    """Return the delay in whole seconds, or None when it cannot be known."""
    if status is TripStatus.CANCELLED or expected is None:
        return None
    return int((expected - scheduled).total_seconds())


def categorize_delay(delay_seconds: int | None, status: TripStatus) -> DelayCategory:
    """Bucket a delay into the categories used by the kiosk UI."""
    if status is TripStatus.CANCELLED:
        return DelayCategory.CANCELLED
    if delay_seconds is None or delay_seconds <= ON_TIME_THRESHOLD_SECONDS:
        return DelayCategory.ON_TIME
    if delay_seconds <= MINOR_THRESHOLD_SECONDS:
        return DelayCategory.MINOR
    if delay_seconds <= MAJOR_THRESHOLD_SECONDS:
        return DelayCategory.MAJOR
    return DelayCategory.SEVERE


def enrich_departure(
    record: ValidDeparture,
    *,
    observed_at: datetime | None = None,
) -> DelayEvent:
    """Turn a validated departure into a delay event."""
    delay_seconds = compute_delay_seconds(
        record.scheduled_time,
        record.expected_time,
        record.status,
    )
    return DelayEvent(
        trip_id=record.trip_id,
        route_id=record.route_id,
        stop_id=record.stop_id,
        scheduled_time=record.scheduled_time,
        expected_time=record.expected_time,
        delay_seconds=delay_seconds,
        delay_category=categorize_delay(delay_seconds, record.status),
        status=record.status,
        observed_at=observed_at or datetime.now(UTC),
    )


def enrich_departures(
    records: Iterable[ValidDeparture],
    *,
    observed_at: datetime | None = None,
) -> list[DelayEvent]:
    """Enrich every validated departure in a batch."""
    timestamp = observed_at or datetime.now(UTC)
    return [enrich_departure(record, observed_at=timestamp) for record in records]


def stops_from_payload(records: Iterable[dict[str, object]]) -> list[Stop]:
    """Build domain stops from raw stop payloads."""
    stops: list[Stop] = []
    for record in records:
        stop_id = record.get("stopId") or record.get("stop_id")
        name = record.get("name")
        if not isinstance(stop_id, str) or not stop_id or not isinstance(name, str):
            continue
        latitude = record.get("latitude")
        longitude = record.get("longitude")
        stops.append(
            Stop(
                stop_id=stop_id,
                name=name,
                latitude=float(latitude) if isinstance(latitude, (int, float)) else None,
                longitude=float(longitude) if isinstance(longitude, (int, float)) else None,
            )
        )
    return stops


def routes_from_departures(records: Iterable[ValidDeparture]) -> list[Route]:
    """Derive unique route metadata from validated departures."""
    routes: dict[str, Route] = {}
    for record in records:
        if record.route_id in routes:
            continue
        routes[record.route_id] = Route(
            route_id=record.route_id,
            short_name=record.route_short_name or record.route_id,
            mode=record.route_mode or "unknown",
        )
    return list(routes.values())
