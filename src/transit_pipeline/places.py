"""Local static catalog of German stops for offline autocomplete."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=2)
def load_stop_catalog(path: Path) -> tuple[dict[str, Any], ...]:
    """Load and cache the generated stop catalog."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(document, list):
        return ()
    return tuple(item for item in document if isinstance(item, dict))


def find_stop(catalog: tuple[dict[str, Any], ...], stop_id: str) -> dict[str, Any] | None:
    for stop in catalog:
        if str(stop.get("id")) == stop_id:
            return stop
    return None


def search_stops(
    catalog: tuple[dict[str, Any], ...],
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Return stops whose names start with or contain the query."""
    needle = query.strip().casefold()
    if len(needle) < 2:
        return []

    starts: list[dict[str, Any]] = []
    contains: list[dict[str, Any]] = []
    for stop in catalog:
        name = str(stop.get("name") or "").casefold()
        if name.startswith(needle):
            starts.append(stop)
            if len(starts) >= limit:
                break
        elif needle in name and len(contains) < limit:
            contains.append(stop)
    return (starts + contains)[:limit]
