from __future__ import annotations

import json
from pathlib import Path

from lib.audit_seed_alias_matches import build_audit
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
                },
                {
                    "canonical_id": "reuters",
                    "label": "org.ent.pressagency.reuters",
                    "display_name": "Reuters",
                    "aliases": ["Reuters"],
                    "trainable": True,
                },
            ]
        ),
        encoding="utf-8",
    )


def test_audit_seed_alias_matches_classifies_match_quality(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    metadata = tmp_path / "newsagency_seeds.json"
    write_metadata(metadata)
    write_jsonl(
        source,
        [
            {
                "id": "exact-doc",
                "language": "fr",
                "date": "1946-01-01",
                "newspaper": "JDG",
                "text": "Selon Havas.",
                "tokens": ["Selon", "Havas", "."],
                "token_start_offsets": [0, 6, 11],
                "token_end_offsets": [5, 11, 12],
                "entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "surface": "Havas",
                        "token_start": 1,
                        "token_stop": 2,
                    }
                ],
            },
            {
                "id": "boundary-doc",
                "language": "fr",
                "date": "1946-01-01",
                "newspaper": "JDG",
                "text": "Selon Agence Havas.",
                "tokens": ["Selon", "Agence", "Havas", "."],
                "token_start_offsets": [0, 6, 13, 18],
                "token_end_offsets": [5, 12, 18, 19],
                "entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "surface": "Havas",
                        "token_start": 2,
                        "token_stop": 3,
                    }
                ],
            },
            {
                "id": "conflict-doc",
                "language": "fr",
                "date": "1946-01-01",
                "newspaper": "JDG",
                "text": "Selon Havas.",
                "tokens": ["Selon", "Havas", "."],
                "token_start_offsets": [0, 6, 11],
                "token_end_offsets": [5, 11, 12],
                "entities": [
                    {
                        "label": "org.ent.pressagency.reuters",
                        "surface": "Havas",
                        "token_start": 1,
                        "token_stop": 2,
                    }
                ],
            },
            {
                "id": "fp-doc",
                "language": "fr",
                "date": "1946-01-01",
                "newspaper": "JDG",
                "text": "Selon Havas.",
                "tokens": ["Selon", "Havas", "."],
                "token_start_offsets": [0, 6, 11],
                "token_end_offsets": [5, 11, 12],
                "entities": [],
            },
        ],
    )

    rows, summary = build_audit(split_inputs=[("train", source)], metadata_paths=[metadata], context_chars=20)

    by_doc = {(row["document_id"], row["alias"]): row["outcome"] for row in rows}
    assert by_doc[("exact-doc", "Havas")] == "exact"
    assert by_doc[("boundary-doc", "Agence Havas")] == "same_label_overlap"
    assert by_doc[("conflict-doc", "Havas")] == "label_conflict"
    assert by_doc[("fp-doc", "Havas")] == "false_positive"
    assert summary["by_outcome"] == {
        "exact": 1,
        "false_positive": 1,
        "label_conflict": 1,
        "same_label_overlap": 1,
    }
    havas_quality = [item for item in summary["alias_quality"] if item["alias"] == "Havas"][0]
    assert havas_quality["hits"] == 3
    assert havas_quality["precision_exact"] == 0.3333
