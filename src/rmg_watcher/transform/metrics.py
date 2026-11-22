"""Punctuality statistics, percentiles, top-k delays, and transfer risk graph."""

from __future__ import annotations

import heapq
import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from rmg_watcher.constants import DEFAULT_MAX_WAIT_SECONDS, DEFAULT_TOP_K, PERCENT_MAX
from rmg_watcher.domain.models import DelayEvent, TripStatus

PUNCTUALITY_THRESHOLD_SECONDS = 300


@dataclass(frozen=True, slots=True)
class MetricsSummary:
    """Aggregate delay metrics for the kiosk UI."""

    total_events: int
    punctuality_rate: float
    median_delay_seconds: float | None
    p95_delay_seconds: float | None
    top_delayed_routes: list[tuple[str, int]]
    route_names: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransferRisk:
    """Projected risk of missing a connection at a stop."""

    stop_id: str
    inbound_route_id: str
    outbound_route_id: str
    stop_name: str | None = None
    inbound_route_name: str | None = None
    outbound_route_name: str | None = None
    scheduled_transfer_seconds: int = 0
    projected_slack_seconds: int = 0
    at_risk: bool = False


def percentile(values: Sequence[float], rank: float) -> float | None:
    """Return a linearly interpolated percentile for ``rank`` in 0..100."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])

    position = (len(ordered) - 1) * (rank / PERCENT_MAX)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])

    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def punctuality_rate(
    events: Sequence[DelayEvent],
    *,
    threshold_seconds: int = PUNCTUALITY_THRESHOLD_SECONDS,
) -> float:
    """Return the share of non-cancelled events within the delay threshold."""
    if not events:
        return 0.0
    punctual = sum(
        1
        for event in events
        if event.status is not TripStatus.CANCELLED
        and event.delay_seconds is not None
        and event.delay_seconds <= threshold_seconds
    )
    return punctual / len(events)


def delay_values(events: Sequence[DelayEvent]) -> list[float]:
    """Return the non-null delay values in seconds."""
    return [
        float(event.delay_seconds)
        for event in events
        if event.delay_seconds is not None
    ]


def top_delayed_routes(
    events: Sequence[DelayEvent],
    *,
    limit: int = DEFAULT_TOP_K,
) -> list[tuple[str, int]]:
    """Return the routes with the largest observed delay."""
    worst: dict[str, int] = {}
    for event in events:
        if event.delay_seconds is None:
            continue
        worst[event.route_id] = max(worst.get(event.route_id, 0), event.delay_seconds)
    return heapq.nlargest(limit, worst.items(), key=lambda item: item[1])


def summarize_metrics(
    events: Sequence[DelayEvent],
    *,
    limit: int = DEFAULT_TOP_K,
    threshold_seconds: int = PUNCTUALITY_THRESHOLD_SECONDS,
) -> MetricsSummary:
    """Compute the metrics summary shown by the kiosk UI."""
    delays = delay_values(events)
    return MetricsSummary(
        total_events=len(events),
        punctuality_rate=punctuality_rate(events, threshold_seconds=threshold_seconds),
        median_delay_seconds=percentile(delays, 50),
        p95_delay_seconds=percentile(delays, 95),
        top_delayed_routes=top_delayed_routes(events, limit=limit),
    )


def assess_transfer_risks(
    events: Sequence[DelayEvent],
    *,
    min_transfer_seconds: int = 180,
    max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS,
) -> list[TransferRisk]:
    """Pair inbound and outbound trips at each stop and score their slack."""
    by_stop: dict[str, list[DelayEvent]] = {}
    for event in events:
        by_stop.setdefault(event.stop_id, []).append(event)

    risks: list[TransferRisk] = []
    for stop_id, stop_events in by_stop.items():
        ordered = sorted(stop_events, key=lambda event: event.scheduled_time)
        for index, inbound in enumerate(ordered):
            inbound_time = inbound.expected_time or inbound.scheduled_time
            for outbound in ordered[index + 1 :]:
                if outbound.route_id == inbound.route_id:
                    continue

                scheduled_transfer = int(
                    (outbound.scheduled_time - inbound.scheduled_time).total_seconds()
                )
                if scheduled_transfer < min_transfer_seconds:
                    continue
                if scheduled_transfer > max_wait_seconds:
                    break

                slack = (
                    int((outbound.scheduled_time - inbound_time).total_seconds())
                    - min_transfer_seconds
                )
                risks.append(
                    TransferRisk(
                        stop_id=stop_id,
                        inbound_route_id=inbound.route_id,
                        outbound_route_id=outbound.route_id,
                        scheduled_transfer_seconds=scheduled_transfer,
                        projected_slack_seconds=slack,
                        at_risk=slack < 0,
                    )
                )

    return sorted(risks, key=lambda risk: risk.projected_slack_seconds)
