import csv
import json
from pathlib import Path

from lib.audit_predicted_iob import audit_rows, main


def row(document_id: str, token_index: int, token: str, gold_label: str, pred_label: str) -> dict[str, str]:
    return {
        "split": "test",
        "document_id": document_id,
        "language": "de",
        "date": "1942-11-12",
        "newspaper": "DTT",
        "token_index": str(token_index),
        "token": token,
        "gold_label": gold_label,
        "pred_label": pred_label,
        "pred_confidence": "0.900000",
    }


def test_audit_predicted_iob_counts_illegal_transitions() -> None:
    rows = [
        row("doc1", 0, "Reuters", "B-org.ent.pressagency.reuters", "I-org.ent.pressagency.reuters"),
        row("doc1", 1, "meldet", "O", "O"),
        row("doc1", 2, "Havas", "O", "I-org.ent.pressagency.havas"),
        row("doc1", 3, "AFP", "B-org.ent.pressagency.afp", "B-org.ent.pressagency.afp"),
        row("doc1", 4, "DNB", "B-org.ent.pressagency.dnb", "I-org.ent.pressagency.dnb"),
    ]

    summary, violations = audit_rows(rows)

    assert summary["documents"] == 1
    assert summary["predicted_entity_tokens"] == 4
    assert summary["predicted_entities"] == 4
    assert summary["illegal_transitions"] == 3
    assert summary["affected_documents"] == 1
    assert summary["violations_by_type"] == {
        "O_to_I": 1,
        "different_label_to_I": 1,
        "sequence_start_to_I": 1,
    }
    assert summary["violations_by_predicted_label"] == {
        "org.ent.pressagency.dnb": 1,
        "org.ent.pressagency.havas": 1,
        "org.ent.pressagency.reuters": 1,
    }
    assert summary["violations_by_gold_label"]["B-org.ent.pressagency.reuters"] == 1
    assert violations[0]["previous_pred_label"] == "<START>"
    assert violations[0]["violation_type"] == "sequence_start_to_I"


def test_audit_predicted_iob_cli_writes_summary_and_violations(tmp_path: Path) -> None:
    input_tsv = tmp_path / "test_token_predictions.tsv"
    summary_json = tmp_path / "summary.json"
    violations_tsv = tmp_path / "violations.tsv"
    rows = [
        row("doc1", 0, "Reuters", "O", "O"),
        row("doc1", 1, "Havas", "B-org.ent.pressagency.havas", "I-org.ent.pressagency.havas"),
    ]
    with input_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    assert main(
        [
            "--token-predictions",
            str(input_tsv),
            "--summary-json",
            str(summary_json),
            "--violations-tsv",
            str(violations_tsv),
        ]
    ) == 0

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["illegal_transitions"] == 1
    assert "previous_pred_label\tpred_label\tpred_confidence\tviolation_type" in violations_tsv.read_text(encoding="utf-8")
