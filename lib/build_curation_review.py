from __future__ import annotations

import argparse
import hashlib
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


def load_decisions(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    decisions: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        review_id = row.get("review_id")
        if review_id:
            decisions[review_id] = row
    return decisions


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
    token_start_offsets = row.get("token_start_offsets", [])
    token_end_offsets = row.get("token_end_offsets", [])
    char_start = token_start_offsets[start] if start < len(token_start_offsets) else None
    char_stop = token_end_offsets[stop - 1] if stop - 1 < len(token_end_offsets) else None
    surface = natural_text(row, start, stop)
    return {
        "label": label,
        "token_start": start,
        "token_stop": stop,
        "surface": surface,
        "char_start": char_start,
        "char_stop": char_stop,
    }


def natural_text(row: dict[str, Any], start: int, stop: int) -> str:
    token_start_offsets = row.get("token_start_offsets", [])
    token_end_offsets = row.get("token_end_offsets", [])
    text = row.get("text")
    if (
        isinstance(text, str)
        and start < len(token_start_offsets)
        and stop > start
        and stop - 1 < len(token_end_offsets)
    ):
        return text[token_start_offsets[start] : token_end_offsets[stop - 1]]
    return render_tokens(row["tokens"][start:stop], row.get("token_render", [])[start:stop])


def render_tokens(tokens: list[str], token_render: list[str] | None = None) -> str:
    token_render = token_render or [""] * len(tokens)
    parts = []
    for index, token in enumerate(tokens):
        parts.append(token)
        render = token_render[index] if index < len(token_render) else ""
        if "NoSpaceAfter" not in render and index != len(tokens) - 1:
            parts.append(" ")
    return "".join(parts)


def context(row: dict[str, Any], entities: list[Entity], radius: int) -> dict[str, Any]:
    tokens = row["tokens"]
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
        "token_render": row.get("token_render", [])[start:stop],
        "text": natural_text(row, start, stop),
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
    decisions: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    source_by_id = {row["id"]: row for row in source_rows}
    out: list[dict[str, Any]] = []
    decisions = decisions or {}
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
            out.append(review_item(split, issue_type, source, gold, pred, context_radius, decisions))

        for pred in remaining_pred:
            if pred in matched_pred:
                continue
            out.append(review_item(split, "extra_prediction", source, None, pred, context_radius, decisions))
    return out


def review_item(
    split: str,
    issue_type: str,
    source: dict[str, Any],
    gold: Entity | None,
    pred: Entity | None,
    context_radius: int,
    decisions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    entities = [entity for entity in (gold, pred) if entity is not None]
    review_id = stable_review_id(split, issue_type, source["id"], gold, pred)
    decision = decisions.get(review_id, {})
    return {
        "review_id": review_id,
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
        "context": context(source, entities, context_radius),
        "decision": {
            "status": decision.get("status", "todo"),
            "choice": decision.get("choice", ""),
            "correct_label": decision.get("correct_label", ""),
            "notes": decision.get("notes", ""),
            "reviewer": decision.get("reviewer", ""),
            "reviewed_at": decision.get("reviewed_at", ""),
        },
    }


def stable_review_id(split: str, issue_type: str, doc_id: str, gold: Entity | None, pred: Entity | None) -> str:
    payload = {
        "split": split,
        "doc_id": doc_id,
        "issue_type": issue_type,
        "gold": entity_key(gold),
        "prediction": entity_key(pred),
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return f"{split}:{doc_id}:{digest}"


def entity_key(entity: Entity | None) -> dict[str, Any] | None:
    if entity is None:
        return None
    start, stop, label = entity
    return {"token_start": start, "token_stop": stop, "label": label}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"total": len(rows), "by_split": {}, "by_language": {}, "by_issue_type": {}, "by_status": {}}
    for row in rows:
        fields = [
            ("by_split", row["split"]),
            ("by_language", row["language"]),
            ("by_issue_type", row["issue_type"]),
            ("by_status", row["decision"]["status"]),
        ]
        for key, value in fields:
            summary[key][value] = summary[key].get(value, 0) + 1
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build manual curation review JSONL from evaluation predictions.")
    parser.add_argument("--train-jsonl", default="")
    parser.add_argument("--train-predictions", default="")
    parser.add_argument("--validation-jsonl", default="")
    parser.add_argument("--validation-predictions", default="")
    parser.add_argument("--test-jsonl", default="")
    parser.add_argument("--test-predictions", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decisions-jsonl", default="")
    parser.add_argument("--languages", default="de fr")
    parser.add_argument("--context-radius", type=int, default=20)
    parser.add_argument("--splits", default="train validation test", help='Whitespace-separated subset, e.g. "train", "validation", or "test".')
    return parser.parse_args(argv)


def selected_split_inputs(args: argparse.Namespace) -> list[tuple[str, Path, Path]]:
    available = {
        "train": (args.train_jsonl, args.train_predictions),
        "validation": (args.validation_jsonl, args.validation_predictions),
        "test": (args.test_jsonl, args.test_predictions),
    }
    selected = args.splits.split()
    unknown = sorted(set(selected) - set(available))
    if unknown:
        raise ValueError(f"unknown split(s): {', '.join(unknown)}")

    out = []
    for split in selected:
        source, predictions = available[split]
        if not source or not predictions:
            raise ValueError(f"{split} requires --{split}-jsonl and --{split}-predictions")
        out.append((split, Path(source), Path(predictions)))
    return out


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    languages = set(args.languages.split())
    decisions = load_decisions(Path(args.decisions_jsonl) if args.decisions_jsonl else None)
    all_rows: list[dict[str, Any]] = []
    for split, source_path, prediction_path in selected_split_inputs(args):
        rows = build_disagreements(
            split,
            load_jsonl(source_path),
            load_jsonl(prediction_path),
            languages=languages,
            context_radius=args.context_radius,
            decisions=decisions,
        )
        write_jsonl(output_dir / f"{split}_disagreements.jsonl", rows)
        for language in sorted(languages):
            write_jsonl(output_dir / f"{split}_{language}_disagreements.jsonl", [row for row in rows if row["language"] == language])
        all_rows.extend(rows)

    write_jsonl(output_dir / "all_disagreements.jsonl", all_rows)
    write_jsonl(output_dir / "todo_disagreements.jsonl", [row for row in all_rows if row["decision"]["status"] == "todo"])
    write_json(output_dir / "summary.json", summarize(all_rows))
    print(json.dumps(summarize(all_rows), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
