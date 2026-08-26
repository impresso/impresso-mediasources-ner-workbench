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


def entity_type(label: str) -> str:
    return "" if label in {"", "O", "IGNORED"} else base_label(label)


def prefix(label: str) -> str:
    if label.startswith("B-"):
        return "B"
    if label.startswith("I-"):
        return "I"
    return "O"


def legal_word_expansion(labels: list[str]) -> bool:
    if not labels:
        return True
    if all(label == "O" for label in labels):
        return True
    first = labels[0]
    if not first.startswith(("B-", "I-")):
        return False
    label_type = base_label(first)
    return all(label == f"I-{label_type}" for label in labels[1:])


def expansion_pattern(labels: list[str]) -> str:
    if not labels:
        return "empty"
    if all(label == "O" for label in labels):
        return "all_O"
    types = [entity_type(label) for label in labels if entity_type(label)]
    unique_types = set(types)
    if len(unique_types) > 1:
        return "mixed_entity_types"
    if labels[0] == "O" and types:
        return "first_O_continuation_entity"
    if any(label == "O" for label in labels[1:]):
        return "internal_O"
    if legal_word_expansion(labels):
        return f"valid_{prefix(labels[0])}"
    return "invalid_bio_shape"


def confidence_values(rows: list[dict[str, str]]) -> list[float]:
    out = []
    for row in rows:
        try:
            out.append(float(row.get("pred_confidence", "0") or 0.0))
        except ValueError:
            out.append(0.0)
    return out


def classify_word(rows: list[dict[str, str]]) -> dict[str, str]:
    first = rows[0]
    labels = [row["pred_label"] for row in rows]
    entity_types = [entity_type(label) for label in labels if entity_type(label)]
    unique_entity_types = sorted(set(entity_types))
    confidences = confidence_values(rows)
    first_type = entity_type(labels[0])
    continuation_types = [entity_type(label) for label in labels[1:] if entity_type(label)]
    continuation_unique = sorted(set(continuation_types))
    pattern = expansion_pattern(labels)
    type_agreement = "none"
    if entity_types:
        type_agreement = "agree" if len(unique_entity_types) == 1 else "disagree"
    first_vs_continuation = ""
    if labels[0] == "O" and continuation_types:
        first_vs_continuation = "first_O_continuation_entity"
    elif first_type and not continuation_types and len(labels) > 1:
        first_vs_continuation = "first_entity_continuation_O"
    elif first_type and continuation_unique and (len(continuation_unique) > 1 or continuation_unique[0] != first_type):
        first_vs_continuation = "first_type_differs_from_continuation"

    return {
        "document_id": first["document_id"],
        "language": first.get("language", ""),
        "date": first.get("date", ""),
        "newspaper": first.get("newspaper", ""),
        "window_index": first["window_index"],
        "window_start_word": first["window_start_word"],
        "absolute_word_index": first["absolute_word_index"],
        "word": first.get("word", ""),
        "subtoken_count": str(len(rows)),
        "gold_loss_labels": " ".join(row["gold_loss_label"] for row in rows),
        "pred_labels": " ".join(labels),
        "pred_entity_types": " ".join(unique_entity_types),
        "pred_confidences": " ".join(f"{value:.6f}" for value in confidences),
        "legal_expansion": str(int(legal_word_expansion(labels))),
        "expansion_pattern": pattern,
        "entity_type_agreement": type_agreement,
        "first_vs_continuation": first_vs_continuation,
    }


def audit_rows(rows: list[dict[str, str]]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    by_word: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("word_id") == "-1" or row.get("absolute_word_index") == "-1":
            continue
        key = (row["document_id"], row["window_index"], row["absolute_word_index"])
        by_word.setdefault(key, []).append(row)
    for word_rows in by_word.values():
        word_rows.sort(key=lambda row: int(row["subtoken_index"]))

    detail_rows = []
    pattern_counts = Counter()
    type_agreement_counts = Counter()
    first_vs_continuation_counts = Counter()
    affected_documents = set()
    multi_subtoken_words = 0
    entity_subtoken_words = 0
    valid_expansions = 0
    invalid_expansions = 0

    for word_rows in by_word.values():
        classification = classify_word(word_rows)
        is_multi = len(word_rows) > 1
        has_entity_subtoken = bool(classification["pred_entity_types"])
        if is_multi:
            multi_subtoken_words += 1
        if has_entity_subtoken:
            entity_subtoken_words += 1
        if classification["legal_expansion"] == "1":
            valid_expansions += 1
        else:
            invalid_expansions += 1
            affected_documents.add(classification["document_id"])
        pattern_counts[classification["expansion_pattern"]] += 1
        type_agreement_counts[classification["entity_type_agreement"]] += 1
        if classification["first_vs_continuation"]:
            first_vs_continuation_counts[classification["first_vs_continuation"]] += 1
        if (
            not classification["legal_expansion"] == "1"
            or classification["entity_type_agreement"] == "disagree"
            or classification["first_vs_continuation"]
        ):
            detail_rows.append(classification)

    summary = {
        "word_instances": len(by_word),
        "multi_subtoken_word_instances": multi_subtoken_words,
        "entity_subtoken_word_instances": entity_subtoken_words,
        "valid_word_expansions": valid_expansions,
        "invalid_word_expansions": invalid_expansions,
        "affected_documents": len(affected_documents),
        "expansion_patterns": dict(sorted(pattern_counts.items())),
        "entity_type_agreement": dict(sorted(type_agreement_counts.items())),
        "first_vs_continuation": dict(sorted(first_vs_continuation_counts.items())),
    }
    return summary, sorted(
        detail_rows,
        key=lambda row: (
            row["document_id"],
            int(row["window_index"]),
            int(row["absolute_word_index"]),
        ),
    )


def load_subtoken_predictions(path: Path) -> list[dict[str, str]]:
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
        "window_index",
        "window_start_word",
        "absolute_word_index",
        "word",
        "subtoken_count",
        "gold_loss_labels",
        "pred_labels",
        "pred_entity_types",
        "pred_confidences",
        "legal_expansion",
        "expansion_pattern",
        "entity_type_agreement",
        "first_vs_continuation",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit raw subtoken prediction consistency within each word.")
    parser.add_argument("--subtoken-predictions", required=True, help="Subtoken prediction TSV produced by evaluation diagnostics.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--details-tsv", required=True)
    args = parser.parse_args(argv)

    summary, details = audit_rows(load_subtoken_predictions(Path(args.subtoken_predictions)))
    write_json(Path(args.summary_json), summary)
    write_tsv(Path(args.details_tsv), details)
    print(json.dumps({**summary, "summary_json": args.summary_json, "details_tsv": args.details_tsv}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
