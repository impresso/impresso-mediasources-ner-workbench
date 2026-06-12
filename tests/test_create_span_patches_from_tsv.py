import json
from pathlib import Path

from lib.apply_span_patch_decisions import apply_span_patches
import pytest

from lib.create_span_patches_from_tsv import (
    actionable_matches,
    build_accepted_patches,
    find_token_matches,
    parse_match_selection,
    parse_tsv_paste,
    resolve_label,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_parse_tsv_paste_reads_comments_and_token_column() -> None:
    sequence = parse_tsv_paste(
        "# document_id = doc-1\n"
        "TOKEN\tNERTAG\n"
        "Agence\tO\n"
        "Havas\tO\n"
    )

    assert sequence.metadata["document_id"] == "doc-1"
    assert sequence.tokens == ("Agence", "Havas")


def test_parse_tsv_paste_accepts_whitespace_separated_columns() -> None:
    sequence = parse_tsv_paste("Deutsche        O\nWelle   O\n")

    assert sequence.tokens == ("Deutsche", "Welle")


def test_find_token_matches_accepts_multiple_hits() -> None:
    sequence = parse_tsv_paste("Havas\tO\n")
    rows = [{"id": "doc-1", "tokens": ["Havas", "et", "Havas"]}]

    matches = find_token_matches(rows, sequence)

    assert [(match.token_start, match.token_stop) for match in matches] == [(0, 1), (2, 3)]


def test_actionable_matches_skips_already_correct_label() -> None:
    sequence = parse_tsv_paste("Deutsche O\nWelle O\n")
    rows = [
        {
            "id": "done",
            "tokens": ["Deutsche", "Welle"],
            "token_labels": [
                "B-org.ent.radiostation.deutsche-welle",
                "I-org.ent.radiostation.deutsche-welle",
            ],
        },
        {
            "id": "todo",
            "tokens": ["Deutsche", "Welle"],
            "token_labels": ["O", "O"],
        },
    ]

    matches = actionable_matches(
        find_token_matches(rows, sequence),
        label="org.ent.radiostation.deutsche-welle",
    )

    assert [match.row["id"] for match in matches] == ["todo"]


def test_actionable_matches_for_o_requires_non_o_label() -> None:
    sequence = parse_tsv_paste("Havas O\n")
    rows = [
        {"id": "done", "tokens": ["Havas"], "token_labels": ["O"]},
        {"id": "todo", "tokens": ["Havas"], "token_labels": ["B-org.ent.pressagency.havas"]},
    ]

    matches = actionable_matches(find_token_matches(rows, sequence), label="O")

    assert [match.row["id"] for match in matches] == ["todo"]


def test_parse_match_selection_accepts_numbers_and_ranges() -> None:
    assert parse_match_selection("1,3-4", 5) == [0, 2, 3]
    assert parse_match_selection("all", 3) == [0, 1, 2]
    assert parse_match_selection("", 3) == []


def test_resolve_label_accepts_known_short_alias_only() -> None:
    metadata = {
        "org.ent.pressagency.ata": {
            "canonical_id": "ata",
            "label": "org.ent.pressagency.ata",
        }
    }

    assert resolve_label("ata", metadata) == "org.ent.pressagency.ata"
    assert resolve_label("org.ent.pressagency.ata", metadata) == "org.ent.pressagency.ata"
    assert resolve_label("O", metadata) == "O"
    with pytest.raises(ValueError, match="unknown"):
        resolve_label("org.ent.pressagency.not-real", metadata)


def test_build_accepted_patches_from_tsv_can_be_applied(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "language": "fr",
                "date": "1950-01-01",
                "newspaper": "EXP",
                "text": "Havas et Havas",
                "tokens": ["Havas", "et", "Havas"],
                "token_start_offsets": [0, 6, 9],
                "token_end_offsets": [5, 8, 14],
                "token_labels": ["O", "O", "O"],
                "entities": [],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="havas",
        pasted_tsv="Havas\tO\n",
        reviewer="tester",
        label_metadata={
            "org.ent.pressagency.havas": {
                "canonical_id": "havas",
                "label": "org.ent.pressagency.havas",
            }
        },
    )

    assert summary["matches"] == 2
    assert summary["new_decisions"] == 2
    apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
        target_label="org.ent.pressagency.havas",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert row["token_labels"] == ["B-org.ent.pressagency.havas", "O", "B-org.ent.pressagency.havas"]
    assert [entity["surface"] for entity in row["entities"]] == ["Havas", "Havas"]


def test_build_o_patches_from_tsv_removes_overlapping_entity(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "Agence Havas",
                "tokens": ["Agence", "Havas"],
                "token_start_offsets": [0, 7],
                "token_end_offsets": [6, 12],
                "token_labels": ["B-org.ent.pressagency.havas", "I-org.ent.pressagency.havas"],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.havas",
                        "start": 0,
                        "stop": 12,
                        "surface": "Agence Havas",
                        "token_start": 0,
                        "token_stop": 2,
                    }
                ],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="O",
        pasted_tsv="Agence\tB-org.ent.pressagency.havas\nHavas\tI-org.ent.pressagency.havas\n",
        reviewer="tester",
    )

    assert summary["label"] == "O"
    apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    change = json.loads((tmp_path / "changes.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["token_labels"] == ["O", "O"]
    assert row["entities"] == []
    assert change["label"] == "O"
    assert change["removed_labels"] == "org.ent.pressagency.havas"
