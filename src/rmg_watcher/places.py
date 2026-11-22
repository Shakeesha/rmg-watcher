"""Local static catalog of German stops for offline autocomplete."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
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


STOP_ALIASES = (
    (re.compile(r"\([^)]*\)"), ""),
    (re.compile(r"\bcentral station\b"), "hauptbahnhof"),
    (re.compile(r"\bhbf\b"), "hauptbahnhof"),
)


def _canonical_input(name: str) -> str:
    text = name.casefold()
    for pattern, replacement in STOP_ALIASES:
        text = pattern.sub(replacement, text)
    return text


def stop_name_key(name: str) -> str:
    """Return a comparable key that merges obvious name variants."""
    tokens = re.sub(r"[^a-z0-9\s]", "", _canonical_input(name)).split()
    return "".join(sorted(tokens))


def canonical_stop(stops: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the most readable stop from a set of equivalent variants."""
    if not stops:
        return None

    def score(stop: dict[str, Any]) -> tuple[bool, bool, int, int, int]:
        name = str(stop.get("name") or "")
        identifier = str(stop.get("id") or stop.get("stopId") or "")
        return (
            "hauptbahnhof" in name.casefold(),
            "(" not in name,
            -len(name),
            -len(identifier),
            -identifier.count(":"),
        )

    return max(stops, key=score)


def _normalise(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]", " ", _canonical_input(value)).split())


def search_stops(
    catalog: tuple[dict[str, Any], ...],
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Return stops matching the words in the query, in any order."""
    normalised_query = _normalise(query)
    tokens = normalised_query.split()
    if len(normalised_query) < 2 or not tokens:
        return []

    required = 1 if len(tokens) == 1 else max(2, len(tokens) - 1)
    scored: list[tuple[int, bool, dict[str, Any]]] = []

    for stop in catalog:
        name = _normalise(str(stop.get("name") or ""))
        if not name:
            continue
        score = sum(1 for token in tokens if token in name)
        if score < required:
            continue
        starts = name.startswith(normalised_query)
        scored.append((score, starts, stop))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

    groups: dict[str, list[dict[str, Any]]] = {}
    for _, _, stop in scored:
        key = stop_name_key(str(stop.get("name") or ""))
        groups.setdefault(key, []).append(stop)

    result: list[dict[str, Any]] = []
    for stops in groups.values():
        selected = canonical_stop(stops)
        if selected is not None:
            result.append(selected)
    return result[:limit]
