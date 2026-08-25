import csv
import json
from pathlib import Path

from lib.audit_subtoken_predictions import audit_rows, main


def subtoken(
    document_id: str,
    word_index: int,
    subtoken_index: int,
    word: str,
    pred_label: str,
    *,
    word_id: str | None = None,
) -> dict[str, str]:
    return {
        "split": "validation",
        "document_id": document_id,
        "language": "de",
        "date": "1942-11-12",
        "newspaper": "DTT",
        "window_index": "0",
        "window_start_word": "0",
        "absolute_word_index": str(word_index),
        "word": word,
        "subtoken_index": str(subtoken_index),
        "subtoken": f"sub{subtoken_index}",
        "word_id": str(word_index) if word_id is None else word_id,
        "is_first_subtoken": "1" if subtoken_index == 0 else "0",
        "gold_loss_id": "0",
        "gold_loss_label": "O",
        "pred_label": pred_label,
        "pred_confidence": "0.900000",
        "top_labels": f"{pred_label}:0.900000",
    }


def test_audit_subtoken_predictions_summarizes_expansion_patterns() -> None:
    rows = [
        subtoken("doc1", -1, 0, "", "B-org.ent.pressagency.akp", word_id="-1"),
        subtoken("doc1", 0, 1, "Agentur", "B-org.ent.pressagency.havas"),
        subtoken("doc1", 0, 2, "Agentur", "I-org.ent.pressagency.havas"),
        subtoken("doc1", 1, 3, "Nachrichtenagentur", "O"),
        subtoken("doc1", 1, 4, "Nachrichtenagentur", "I-org.ent.pressagency.reuters"),
        subtoken("doc1", 2, 5, "AssociatedPress", "B-org.ent.pressagency.ap"),
        subtoken("doc1", 2, 6, "AssociatedPress", "I-org.ent.pressagency.reuters"),
    ]

    summary, details = audit_rows(rows)

    assert summary["word_instances"] == 3
    assert summary["multi_subtoken_word_instances"] == 3
    assert summary["entity_subtoken_word_instances"] == 3
    assert summary["valid_word_expansions"] == 1
    assert summary["invalid_word_expansions"] == 2
    assert summary["expansion_patterns"] == {
        "first_O_continuation_entity": 1,
        "mixed_entity_types": 1,
        "valid_B": 1,
    }
    assert summary["entity_type_agreement"] == {"agree": 2, "disagree": 1}
    assert summary["first_vs_continuation"] == {
        "first_O_continuation_entity": 1,
        "first_type_differs_from_continuation": 1,
    }
    assert [row["word"] for row in details] == ["Nachrichtenagentur", "AssociatedPress"]


def test_audit_subtoken_predictions_cli_writes_outputs(tmp_path: Path) -> None:
    input_tsv = tmp_path / "validation_subtoken_predictions.tsv"
    summary_json = tmp_path / "summary.json"
    details_tsv = tmp_path / "details.tsv"
    rows = [
        subtoken("doc1", 0, 0, "Agentur", "O"),
        subtoken("doc1", 0, 1, "Agentur", "I-org.ent.pressagency.havas"),
    ]
    with input_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    assert main(
        [
            "--subtoken-predictions",
            str(input_tsv),
            "--summary-json",
            str(summary_json),
            "--details-tsv",
            str(details_tsv),
        ]
    ) == 0

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["invalid_word_expansions"] == 1
    assert "first_vs_continuation" in details_tsv.read_text(encoding="utf-8").splitlines()[0]
