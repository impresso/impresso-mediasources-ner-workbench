from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def base_label(label: str) -> str:
    if label.startswith(("B-", "I-")):
        return label[2:]
    return label


def predicted_entity_count(labels: list[str]) -> int:
    count = 0
    active = ""
    for label in labels:
        if label == "O":
            active = ""
            continue
        prefix = label[:1] if label.startswith(("B-", "I-")) else "B"
        base = base_label(label)
        if prefix == "B" or active != base:
            count += 1
        active = base
    return count


def violation_type(previous: str | None, current: str) -> str:
    if not current.startswith("I-"):
        return ""
    if previous is None:
        return "sequence_start_to_I"
    if previous == "O":
        return "O_to_I"
    if previous.startswith(("B-", "I-")) and base_label(previous) != base_label(current):
        return "different_label_to_I"
    if not previous.startswith(("B-", "I-")):
        return "malformed_previous_to_I"
    return ""


def audit_rows(rows: list[dict[str, str]]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    by_doc: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_doc.setdefault(row["document_id"], []).append(row)
    for doc_rows in by_doc.values():
        doc_rows.sort(key=lambda row: int(row["token_index"]))

    violations: list[dict[str, str]] = []
    predicted_entity_tokens = 0
    predicted_entities = 0
    malformed_predicted_labels = Counter()
    violations_by_type = Counter()
    violations_by_label = Counter()
    violations_by_gold_label = Counter()
    affected_documents = set()

    for document_id, doc_rows in sorted(by_doc.items()):
        pred_labels = [row["pred_label"] for row in doc_rows]
        predicted_entity_tokens += sum(1 for label in pred_labels if label != "O")
        predicted_entities += predicted_entity_count(pred_labels)
        previous: str | None = None
        for row in doc_rows:
            pred_label = row["pred_label"]
            if pred_label != "O" and not pred_label.startswith(("B-", "I-")):
                malformed_predicted_labels[pred_label] += 1
            violation = violation_type(previous, pred_label)
            if violation:
                detail = {
                    "document_id": document_id,
                    "language": row.get("language", ""),
                    "date": row.get("date", ""),
                    "newspaper": row.get("newspaper", ""),
                    "token_index": row["token_index"],
                    "token": row["token"],
                    "gold_label": row["gold_label"],
                    "previous_pred_label": previous or "<START>",
                    "pred_label": pred_label,
                    "pred_confidence": row.get("pred_confidence", ""),
                    "violation_type": violation,
                }
                violations.append(detail)
                violations_by_type[violation] += 1
                violations_by_label[base_label(pred_label)] += 1
                violations_by_gold_label[row["gold_label"]] += 1
                affected_documents.add(document_id)
            previous = pred_label

    summary = {
        "documents": len(by_doc),
        "predicted_entity_tokens": predicted_entity_tokens,
        "predicted_entities": predicted_entities,
        "illegal_transitions": len(violations),
        "affected_documents": len(affected_documents),
        "violations_by_type": dict(sorted(violations_by_type.items())),
        "violations_by_predicted_label": dict(sorted(violations_by_label.items())),
        "violations_by_gold_label": dict(sorted(violations_by_gold_label.items())),
        "malformed_predicted_labels": dict(sorted(malformed_predicted_labels.items())),
    }
    return summary, violations


def load_token_predictions(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    columns = [
        "document_id",
        "language",
        "date",
        "newspaper",
        "token_index",
        "token",
        "gold_label",
        "previous_pred_label",
        "pred_label",
        "pred_confidence",
        "violation_type",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit illegal BIO/IOB transitions in word-level model predictions.")
    parser.add_argument("--token-predictions", required=True, help="Token-level prediction TSV produced by evaluation diagnostics.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--violations-tsv", required=True)
    args = parser.parse_args(argv)

    summary, violations = audit_rows(load_token_predictions(Path(args.token_predictions)))
    write_json(Path(args.summary_json), summary)
    write_tsv(Path(args.violations_tsv), violations)
    print(json.dumps({**summary, "summary_json": args.summary_json, "violations_tsv": args.violations_tsv}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
