from __future__ import annotations

import json
from pathlib import Path

from lib.audit_missing_spans import build_candidates
from lib.snippet_data import write_jsonl


def write_metadata(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "havas",
                    "label": "org.ent.pressagency.havas",
                    "display_name": "Havas",
                    "aliases": ["Havas", "Agence Havas"],
                    "trainable": True,
                }
            ]
        ),
        encoding="utf-8",
    )


def test_audit_missing_spans_suggests_target_alias(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    metadata = tmp_path / "newsagency_seeds.json"
    write_metadata(metadata)
    write_jsonl(
        source,
        [
            {
                "id": "doc-1",
                "language": "fr",
                "date": "1946-01-01",
                "newspaper": "JDG",
                "text": "Selon Havas, la nouvelle arrive.",
                "tokens": ["Selon", "Havas", ",", "la", "nouvelle", "arrive", "."],
                "token_start_offsets": [0, 6, 11, 13, 16, 25, 31],
                "token_end_offsets": [5, 11, 12, 15, 24, 31, 32],
                "entities": [],
            }
        ],
    )

    candidates, tsv_rows, summary = build_candidates(
        input_jsonl=source,
        target_label="org.ent.pressagency.havas",
        metadata_paths=[metadata],
        audit_id="missing-spans-org-ent-pressagency-havas-train",
        split="train",
        use_model=False,
        use_patterns=True,
    )

    assert summary["candidate_spans"] == 1
    assert candidates[0]["candidate_spans"][0]["surface"] == "Havas"
    assert candidates[0]["candidate_spans"][0]["token_start"] == 1
    assert tsv_rows[0]["source"] == "pattern"


def test_audit_missing_spans_skips_existing_overlap(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    metadata = tmp_path / "newsagency_seeds.json"
    write_metadata(metadata)
    write_jsonl(
        source,
        [
            {
                "id": "doc-1",
                "language": "fr",
                "date": "1946-01-01",
                "newspaper": "JDG",
                "text": "Selon Havas, la nouvelle arrive.",
                "tokens": ["Selon", "Havas", ",", "la", "nouvelle", "arrive", "."],
                "token_start_offsets": [0, 6, 11, 13, 16, 25, 31],
                "token_end_offsets": [5, 11, 12, 15, 24, 31, 32],
                "entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "start": 6,
                        "stop": 11,
                        "surface": "Havas",
                        "token_start": 1,
                        "token_stop": 2,
                    }
                ],
            }
        ],
    )

    candidates, tsv_rows, summary = build_candidates(
        input_jsonl=source,
        target_label="org.ent.pressagency.havas",
        metadata_paths=[metadata],
        audit_id="missing-spans-org-ent-pressagency-havas-train",
        split="train",
        use_model=False,
        use_patterns=True,
    )

    assert candidates == []
    assert tsv_rows == []
    assert summary["candidate_spans"] == 0
