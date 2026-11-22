"""Hash and set based deduplication of repeated trip status updates."""

from __future__ import annotations

from collections.abc import Iterable

from rmg_watcher.transform.validator import ValidDeparture


def deduplicate_departures(
    records: Iterable[ValidDeparture],
) -> tuple[list[ValidDeparture], int]:
    """Keep the last update per ``(trip_id, stop_id)`` and count removals."""
    unique: dict[tuple[str, str], ValidDeparture] = {}
    duplicates = 0

    for record in records:
        key = (record.trip_id, record.stop_id)
        if key in unique:
            duplicates += 1
        unique[key] = record

    return list(unique.values()), duplicates
