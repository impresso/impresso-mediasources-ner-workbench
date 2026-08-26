from __future__ import annotations

import json
from pathlib import Path

from lib.validate_jsonl_format import main, validate_row


def valid_row() -> dict:
    return {
        "id": "doc-1",
        "text": "Reuters said.",
        "tokens": ["Reuters", "said", "."],
        "token_labels": ["B-org.ent.pressagency.reuters", "O", "O"],
        "token_start_offsets": [0, 8, 12],
        "token_end_offsets": [7, 12, 13],
        "entities": [
            {
                "entity_family": "pressagency",
                "label": "org.ent.pressagency.reuters",
                "surface": "Reuters",
                "start": 0,
                "stop": 7,
                "token_start": 0,
                "token_stop": 1,
            }
        ],
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_validate_row_accepts_minimal_consistent_row() -> None:
    assert validate_row(valid_row(), line_number=1, path=Path("train.jsonl")) == []


def test_validate_row_rejects_token_offset_mismatch() -> None:
    row = valid_row()
    row["token_end_offsets"][0] = 6

    errors = validate_row(row, line_number=1, path=Path("train.jsonl"))

    assert any("token offset mismatch" in error for error in errors)


def test_validate_row_rejects_entity_surface_mismatch() -> None:
    row = valid_row()
    row["entities"][0]["surface"] = "Reuter"

    errors = validate_row(row, line_number=1, path=Path("train.jsonl"))

    assert any("surface mismatch" in error for error in errors)


def test_validate_row_rejects_bio_entity_mismatch() -> None:
    row = valid_row()
    row["entities"] = []

    errors = validate_row(row, line_number=1, path=Path("train.jsonl"))

    assert any("entities missing BIO spans" in error for error in errors)


def test_validate_row_rejects_token_label_ids_by_default() -> None:
    row = valid_row()
    row["token_label_ids"] = [1, 0, 0]

    errors = validate_row(row, line_number=1, path=Path("train.jsonl"))

    assert any("token_label_ids is present" in error for error in errors)


def test_validate_row_can_allow_token_label_ids() -> None:
    row = valid_row()
    row["token_label_ids"] = [1, 0, 0]

    errors = validate_row(row, line_number=1, path=Path("train.jsonl"), allow_token_label_ids=True)

    assert errors == []


def test_validate_jsonl_format_cli_accepts_one_patched_file(tmp_path: Path) -> None:
    path = tmp_path / "patched.jsonl"
    summary = tmp_path / "summary.json"
    write_jsonl(path, [valid_row()])

    assert main(["--jsonl", str(path), "--summary-json", str(summary)]) == 0
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["files"][str(path)] == {"rows": 1, "errors": 0}
