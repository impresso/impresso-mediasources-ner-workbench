from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.replace_tsv_segment import parse_tsv_segment, render_segment, replace_segments


LABEL = "org.ent.pressagency.reuters"


def write_tsv(path: Path, rows: list[tuple[str, str] | tuple[str, str, str]]) -> None:
    path.write_text("\n".join("\t".join(row) for row in rows) + "\n", encoding="utf-8")


def test_parse_tsv_segment_preserves_hyphen_token(tmp_path: Path) -> None:
    path = tmp_path / "segment.tsv"
    write_tsv(path, [("Reu", f"B-{LABEL}"), ("-", f"I-{LABEL}"), ("ter", f"I-{LABEL}")])

    segment = parse_tsv_segment(path)

    assert segment.tokens == ("Reu", "-", "ter")
    assert segment.labels == (f"B-{LABEL}", f"I-{LABEL}", f"I-{LABEL}")
    assert segment.no_space_after == (False, False, False)


def test_render_segment_uses_space_by_default_and_underscore_to_join(tmp_path: Path) -> None:
    path = tmp_path / "segment.tsv"
    write_tsv(
        path,
        [
            ("Reu", f"B-{LABEL}", "_"),
            ("-", f"I-{LABEL}", "_"),
            ("ter", f"I-{LABEL}"),
            ("Zwei", "O"),
        ],
    )

    text, starts, stops = render_segment(parse_tsv_segment(path))

    assert text == "Reu-ter Zwei"
    assert starts == [0, 3, 4, 8]
    assert stops == [3, 4, 7, 12]


def test_replace_segments_replaces_tokens_labels_offsets_entities_and_label_ids(tmp_path: Path) -> None:
    old_path = tmp_path / "old.tsv"
    new_path = tmp_path / "new.tsv"
    write_tsv(
        old_path,
        [
            ("Reu", f"B-{LABEL}"),
            ("-", f"I-{LABEL}"),
            ("terZwei", f"I-{LABEL}"),
        ],
    )
    write_tsv(
        new_path,
        [
            ("Reu", f"B-{LABEL}", "_"),
            ("-", f"I-{LABEL}", "_"),
            ("ter", f"I-{LABEL}"),
            ("Zwei", "O"),
        ],
    )
    old = parse_tsv_segment(old_path)
    new = parse_tsv_segment(new_path)
    rows = [
        {
            "id": "doc-1",
            "text": "Manhattan (Kansas), 30. Nov. (Reu-terZwei)",
            "tokens": ["Manhattan", "(", "Kansas", ")", ",", "30", ".", "Nov", ".", "(", "Reu", "-", "terZwei", ")"],
            "token_start_offsets": [0, 10, 11, 17, 18, 20, 22, 24, 27, 29, 30, 33, 34, 41],
            "token_end_offsets": [9, 11, 17, 18, 19, 22, 23, 27, 28, 30, 33, 34, 41, 42],
            "token_labels": [
                "O",
                "O",
                "O",
                "O",
                "O",
                "O",
                "O",
                "O",
                "O",
                "O",
                f"B-{LABEL}",
                f"I-{LABEL}",
                f"I-{LABEL}",
                "O",
            ],
            "token_label_ids": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 0],
            "entities": [],
        }
    ]

    updated, summary = replace_segments(
        rows,
        old=old,
        new=new,
        label2id={"O": 0, f"B-{LABEL}": 1, f"I-{LABEL}": 2},
    )

    row = updated[0]
    assert summary["replaced"] == 1
    assert row["text"] == "Manhattan (Kansas), 30. Nov. (Reu-ter Zwei)"
    assert row["tokens"][10:14] == ["Reu", "-", "ter", "Zwei"]
    assert row["token_labels"][10:14] == [f"B-{LABEL}", f"I-{LABEL}", f"I-{LABEL}", "O"]
    assert row["token_start_offsets"][10:14] == [30, 33, 34, 38]
    assert row["token_end_offsets"][10:14] == [33, 34, 37, 42]
    assert row["token_label_ids"][10:14] == [1, 2, 2, 0]
    assert row["entities"] == [
        {
            "entity_family": "pressagency",
            "label": LABEL,
            "start": 30,
            "stop": 37,
            "surface": "Reu-ter",
            "token_start": 10,
            "token_stop": 13,
        }
    ]


def test_replace_segments_drops_token_label_ids_by_default(tmp_path: Path) -> None:
    old_path = tmp_path / "old.tsv"
    new_path = tmp_path / "new.tsv"
    write_tsv(old_path, [("AFP", f"B-{LABEL}")])
    write_tsv(new_path, [("AFP", "O")])
    old = parse_tsv_segment(old_path)
    new = parse_tsv_segment(new_path)
    row = {
        "id": "doc-1",
        "text": "AFP",
        "tokens": ["AFP"],
        "token_start_offsets": [0],
        "token_end_offsets": [3],
        "token_labels": [f"B-{LABEL}"],
        "token_label_ids": [1],
        "entities": [],
    }

    updated, _summary = replace_segments([row], old=old, new=new)

    assert "token_label_ids" not in updated[0]
    assert "tsv_segment_replacement" not in updated[0]


def test_replace_segments_projects_offsets_to_most_compact_repeated_ocr_sequence(tmp_path: Path) -> None:
    old_path = tmp_path / "old.tsv"
    new_path = tmp_path / "new.tsv"
    write_tsv(
        old_path,
        [
            ("Reu", f"B-{LABEL}"),
            ("-", f"I-{LABEL}"),
            ("ter", f"I-{LABEL}"),
            ("Zwei", "O"),
        ],
    )
    write_tsv(
        new_path,
        [
            ("Reu", f"B-{LABEL}", "_"),
            ("-", f"I-{LABEL}", "_"),
            ("ter", f"I-{LABEL}"),
            ("Zwei", "O"),
        ],
    )
    old = parse_tsv_segment(old_path)
    new = parse_tsv_segment(new_path)
    row = {
        "id": "doc-1",
        "text": "(( Reu Reu--terZwei rest",
        "tokens": ["Reu", "-", "ter", "Zwei"],
        "token_start_offsets": [3, 10, 12, 15],
        "token_end_offsets": [6, 11, 15, 19],
        "token_labels": [f"B-{LABEL}", f"I-{LABEL}", f"I-{LABEL}", "O"],
        "entities": [],
    }

    updated, _summary = replace_segments([row], old=old, new=new)

    assert updated[0]["text"] == "(( Reu-ter Zwei rest"
    assert updated[0]["token_start_offsets"] == [3, 6, 7, 11]
    assert updated[0]["token_end_offsets"] == [6, 7, 10, 15]
    assert updated[0]["entities"][0]["surface"] == "Reu-ter"


def test_replace_segments_requires_disambiguation_for_multiple_matches(tmp_path: Path) -> None:
    old_path = tmp_path / "old.tsv"
    new_path = tmp_path / "new.tsv"
    write_tsv(old_path, [("AFP", f"B-{LABEL}")])
    write_tsv(new_path, [("AFP", "O")])
    old = parse_tsv_segment(old_path)
    new = parse_tsv_segment(new_path)
    row = {
        "id": "doc-1",
        "text": "AFP AFP",
        "tokens": ["AFP", "AFP"],
        "token_start_offsets": [0, 4],
        "token_end_offsets": [3, 7],
        "token_labels": [f"B-{LABEL}", f"B-{LABEL}"],
        "entities": [],
    }

    with pytest.raises(ValueError, match="matched 2 times"):
        replace_segments([row], old=old, new=new)


def test_replace_segments_can_apply_selected_match_index(tmp_path: Path) -> None:
    old_path = tmp_path / "old.tsv"
    new_path = tmp_path / "new.tsv"
    write_tsv(old_path, [("AFP", f"B-{LABEL}")])
    write_tsv(new_path, [("AFP", "O")])
    old = parse_tsv_segment(old_path)
    new = parse_tsv_segment(new_path)
    row = {
        "id": "doc-1",
        "text": "AFP AFP",
        "tokens": ["AFP", "AFP"],
        "token_start_offsets": [0, 4],
        "token_end_offsets": [3, 7],
        "token_labels": [f"B-{LABEL}", f"B-{LABEL}"],
        "entities": [],
    }

    updated, summary = replace_segments([row], old=old, new=new, match_index=2)

    assert summary["locations"] == [{"id": "doc-1", "token_start": 1}]
    assert updated[0]["token_labels"] == [f"B-{LABEL}", "O"]


def test_replace_tsv_segment_json_round_trip(tmp_path: Path) -> None:
    row = {
        "id": "doc-1",
        "text": "Reu-ter",
        "tokens": ["Reu", "-", "ter"],
        "token_start_offsets": [0, 3, 4],
        "token_end_offsets": [3, 4, 7],
        "token_labels": [f"B-{LABEL}", f"I-{LABEL}", f"I-{LABEL}"],
    }
    assert json.loads(json.dumps(row))["tokens"] == ["Reu", "-", "ter"]
