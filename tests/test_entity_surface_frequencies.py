from __future__ import annotations

from pathlib import Path

from lib.entity_surface_frequencies import build_frequency_report
from lib.snippet_data import write_jsonl


def test_build_frequency_report_groups_case_insensitive_surfaces_by_language(tmp_path: Path) -> None:
    data = tmp_path / "train.jsonl"
    write_jsonl(
        data,
        [
            {
                "id": "doc-1",
                "language": "fr",
                "text": "Havas puis HAVAS.",
                "entities": [
                    {"label": "org.ent.pressagency.havas", "start": 0, "stop": 5, "surface": "Havas"},
                    {"label": "org.ent.pressagency.havas", "start": 11, "stop": 16, "surface": "HAVAS"},
                ],
            },
            {
                "id": "doc-2",
                "language": "de",
                "text": "Agence Havas meldet.",
                "entities": [
                    {"label": "org.ent.pressagency.havas", "start": 0, "stop": 12, "surface": "Agence Havas"},
                ],
            },
        ],
    )

    report = build_frequency_report([data], label="org.ent.pressagency.havas")

    assert report["total"] == 3
    assert report["languages"]["fr"]["surfaces"]["havas"]["count"] == 2
    assert report["languages"]["fr"]["surfaces"]["havas"]["forms"] == {"Havas": 1, "HAVAS": 1}
    assert report["languages"]["de"]["surfaces"]["agence havas"]["count"] == 1
