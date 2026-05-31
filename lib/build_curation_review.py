from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


Entity = tuple[int, int, str]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def strip_bio(label: str) -> str:
    if label == "O":
        return "O"
    if label.startswith(("B-", "I-")):
        return label[2:]
    return label


def labels_to_entities(labels: list[str]) -> set[Entity]:
    entities: set[Entity] = set()
    start: int | None = None
    active = ""

    def close(stop: int) -> None:
        nonlocal start, active
        if start is not None:
            entities.add((start, stop, active))
        start = None
        active = ""

    for index, label in enumerate(labels):
        if label == "O":
            close(index)
            continue
        prefix = label[:1] if label.startswith(("B-", "I-")) else "B"
        base = strip_bio(label)
        if prefix == "B" or start is None or active != base:
            close(index)
            start = index
            active = base
    close(len(labels))
    return entities


def entity_record(entity: Entity | None, row: dict[str, Any]) -> dict[str, Any] | None:
    if entity is None:
        return None
    start, stop, label = entity
    tokens = row["tokens"][start:stop]
    token_start_offsets = row.get("token_start_offsets", [])
    token_end_offsets = row.get("token_end_offsets", [])
    char_start = token_start_offsets[start] if start < len(token_start_offsets) else None
    char_stop = token_end_offsets[stop - 1] if stop - 1 < len(token_end_offsets) else None
    return {
        "label": label,
        "token_start": start,
        "token_stop": stop,
        "surface": " ".join(tokens),
        "char_start": char_start,
        "char_stop": char_stop,
    }


def context(tokens: list[str], entities: list[Entity], radius: int) -> dict[str, Any]:
    if entities:
        start = max(0, min(entity[0] for entity in entities) - radius)
        stop = min(len(tokens), max(entity[1] for entity in entities) + radius)
    else:
        start = 0
        stop = min(len(tokens), radius * 2)
    return {
        "token_start": start,
        "token_stop": stop,
        "tokens": tokens[start:stop],
        "text": " ".join(tokens[start:stop]),
    }


def overlap(left: Entity, right: Entity) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def build_disagreements(
    split: str,
    source_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    *,
    languages: set[str],
    context_radius: int,
) -> list[dict[str, Any]]:
    source_by_id = {row["id"]: row for row in source_rows}
    out: list[dict[str, Any]] = []
    sequence = 0
    for pred_row in prediction_rows:
        source = source_by_id[pred_row["id"]]
        language = source.get("language", pred_row.get("language", ""))
        if language not in languages:
            continue
        gold_entities = labels_to_entities(pred_row["gold_labels"])
        pred_entities = labels_to_entities(pred_row["pred_labels"])
        correct = gold_entities & pred_entities
        remaining_gold = sorted(gold_entities - correct)
        remaining_pred = sorted(pred_entities - correct)
        matched_pred: set[Entity] = set()

        for gold in remaining_gold:
            overlapping = [pred for pred in remaining_pred if pred not in matched_pred and overlap(gold, pred)]
            if overlapping:
                pred = overlapping[0]
                matched_pred.add(pred)
                issue_type = "label_mismatch" if gold[:2] == pred[:2] and gold[2] != pred[2] else "span_or_label_mismatch"
            else:
                pred = None
                issue_type = "missing_prediction"
            sequence += 1
            out.append(review_item(sequence, split, issue_type, source, gold, pred, context_radius))

        for pred in remaining_pred:
            if pred in matched_pred:
                continue
            sequence += 1
            out.append(review_item(sequence, split, "extra_prediction", source, None, pred, context_radius))
    return out


def review_item(
    sequence: int,
    split: str,
    issue_type: str,
    source: dict[str, Any],
    gold: Entity | None,
    pred: Entity | None,
    context_radius: int,
) -> dict[str, Any]:
    entities = [entity for entity in (gold, pred) if entity is not None]
    return {
        "review_id": f"{split}:{sequence:05d}",
        "split": split,
        "language": source.get("language", ""),
        "document": {
            "id": source["id"],
            "newspaper": source.get("newspaper", ""),
            "date": source.get("date", ""),
            "source_file": source.get("source_file", ""),
        },
        "issue_type": issue_type,
        "gold": entity_record(gold, source),
        "prediction": entity_record(pred, source),
        "context": context(source["tokens"], entities, context_radius),
        "decision": {
            "status": "todo",
            "choice": "",
            "correct_label": "",
            "notes": "",
        },
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"total": len(rows), "by_split": {}, "by_language": {}, "by_issue_type": {}}
    for row in rows:
        for key, field in [("by_split", "split"), ("by_language", "language"), ("by_issue_type", "issue_type")]:
            value = row[field]
            summary[key][value] = summary[key].get(value, 0) + 1
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build manual curation review JSONL from evaluation predictions.")
    parser.add_argument("--validation-jsonl", required=True)
    parser.add_argument("--validation-predictions", required=True)
    parser.add_argument("--test-jsonl", required=True)
    parser.add_argument("--test-predictions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--languages", default="de fr")
    parser.add_argument("--context-radius", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    languages = set(args.languages.split())
    all_rows: list[dict[str, Any]] = []
    for split, source_path, prediction_path in [
        ("validation", Path(args.validation_jsonl), Path(args.validation_predictions)),
        ("test", Path(args.test_jsonl), Path(args.test_predictions)),
    ]:
        rows = build_disagreements(
            split,
            load_jsonl(source_path),
            load_jsonl(prediction_path),
            languages=languages,
            context_radius=args.context_radius,
        )
        write_jsonl(output_dir / f"{split}_disagreements.jsonl", rows)
        for language in sorted(languages):
            write_jsonl(output_dir / f"{split}_{language}_disagreements.jsonl", [row for row in rows if row["language"] == language])
        all_rows.extend(rows)

    write_jsonl(output_dir / "all_disagreements.jsonl", all_rows)
    write_json(output_dir / "summary.json", summarize(all_rows))
    print(json.dumps(summarize(all_rows), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
