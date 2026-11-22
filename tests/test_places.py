"""Tests for the local German stop catalog search."""

from __future__ import annotations

from pathlib import Path

from rmg_watcher.places import load_stop_catalog, search_stops


def test_search_merges_station_name_variants() -> None:
    catalog = (
        {
            "id": "1",
            "name": "Darmstadt Hbf",
            "latitude": 49.87,
            "longitude": 8.63,
            "type": "STOP",
        },
        {
            "id": "2",
            "name": "Darmstadt Hauptbahnhof",
            "latitude": 49.87,
            "longitude": 8.63,
            "type": "STOP",
        },
        {
            "id": "3",
            "name": "Darmstadt Central Station (FlixTrain)",
            "latitude": 49.87,
            "longitude": 8.63,
            "type": "STOP",
        },
        {
            "id": "4",
            "name": "Hauptbahnhof, Darmstadt",
            "latitude": 49.87,
            "longitude": 8.63,
            "type": "STOP",
        },
    )

    results = search_stops(catalog, "Darmstadt Hbf", 6)

    assert len(results) == 1
    assert results[0]["name"] == "Darmstadt Hauptbahnhof"


def test_search_handles_spaces_and_punctuation(tmp_path: Path) -> None:
    catalog_path = tmp_path / "german-stops.json"
    catalog_path.write_text(
        '[{"id":"1","name":"Bahnhof, Babenhausen (Hessen)",'
        '"latitude":49.95,"longitude":8.95,"type":"STOP","mode":"train"}]',
        encoding="utf-8",
    )

    catalog = load_stop_catalog(catalog_path)
    results = search_stops(catalog, "Babenhausen (Hess) Bahnhof", 6)

    assert [stop["id"] for stop in results] == ["1"]
