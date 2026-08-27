from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def labels_to_entities(labels: list[str]) -> set[tuple[int, int, str]]:
    entities: set[tuple[int, int, str]] = set()
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
        prefix, separator, entity = label.partition("-")
        if not separator or prefix not in {"B", "I"}:
            close(index)
            continue
        if prefix == "B" or start is None or active != entity:
            close(index)
            start = index
            active = entity
    close(len(labels))
    return entities


def safe_div(num: int | float, den: int | float) -> float:
    return float(num) / float(den) if den else 0.0


def f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def metrics_for(rows: list[dict[str, Any]], pred_by_id: dict[str, list[str]]) -> dict[str, float | int]:
    gold_entities = set()
    pred_entities = set()
    all_gold: list[str] = []
    all_pred: list[str] = []
    for row in rows:
        doc_id = str(row["id"])
        gold_labels = [str(label) for label in row["token_labels"]]
        pred_labels = pred_by_id[doc_id]
        all_gold.extend(gold_labels)
        all_pred.extend(pred_labels)
        for start, stop, label in labels_to_entities(gold_labels):
            gold_entities.add((doc_id, start, stop, label))
        for start, stop, label in labels_to_entities(pred_labels):
            pred_entities.add((doc_id, start, stop, label))
    token_correct = sum(1 for gold, pred in zip(all_gold, all_pred, strict=True) if gold == pred)
    non_o_gold = sum(1 for label in all_gold if label != "O")
    non_o_pred = sum(1 for label in all_pred if label != "O")
    non_o_correct = sum(1 for gold, pred in zip(all_gold, all_pred, strict=True) if gold == pred and gold != "O")
    entity_correct = len(gold_entities & pred_entities)
    entity_precision = safe_div(entity_correct, len(pred_entities))
    entity_recall = safe_div(entity_correct, len(gold_entities))
    token_precision = safe_div(non_o_correct, non_o_pred)
    token_recall = safe_div(non_o_correct, non_o_gold)
    return {
        "token_total": len(all_gold),
        "token_accuracy": safe_div(token_correct, len(all_gold)),
        "token_non_o_gold": non_o_gold,
        "token_non_o_pred": non_o_pred,
        "token_non_o_precision": token_precision,
        "token_non_o_recall": token_recall,
        "token_non_o_f1": f1(token_precision, token_recall),
        "entity_gold": len(gold_entities),
        "entity_pred": len(pred_entities),
        "entity_correct": entity_correct,
        "entity_precision": entity_precision,
        "entity_recall": entity_recall,
        "entity_f1": f1(entity_precision, entity_recall),
    }


def import_runtime():
    try:
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError as exc:
        raise SystemExit("inference parity check requires transformers and torch") from exc
    return AutoModelForTokenClassification, AutoTokenizer


def import_pipeline(pipeline_dir: Path):
    sys.path.insert(0, str(pipeline_dir.resolve()))
    try:
        from pipeline import MediaAgenciesPipeline
    except ImportError as exc:
        raise SystemExit(f"cannot import MediaAgenciesPipeline from {pipeline_dir}") from exc
    return MediaAgenciesPipeline


def resolve_model_source(model: str, *, revision: str | None = None) -> tuple[str, dict[str, str]]:
    path = Path(model).expanduser()
    if path.exists():
        return str(path.resolve()), {}
    return model, {"revision": revision} if revision else {}


def prediction_labels_by_id(predictions: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_id: dict[str, list[str]] = {}
    for row in predictions:
        by_id[str(row["id"])] = [str(label) for label in row["pred_labels"]]
    return by_id


def compare_rows(
    rows: list[dict[str, Any]],
    reference_pred_by_id: dict[str, list[str]],
    pipeline: Any,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    pipeline_pred_by_id: dict[str, list[str]] = {}
    mismatches: list[dict[str, Any]] = []
    for row in rows:
        doc_id = str(row["id"])
        result = pipeline(str(row["text"]))
        expected_tokens = [str(token) for token in row["tokens"]]
        actual_tokens = [str(token) for token in result["tokens"]]
        actual_labels = [str(label) for label in result["token_labels"]]
        reference_labels = reference_pred_by_id.get(doc_id)
        pipeline_pred_by_id[doc_id] = actual_labels
        if expected_tokens != actual_tokens:
            mismatches.append(
                {
                    "id": doc_id,
                    "kind": "tokenization_mismatch",
                    "expected_tokens": expected_tokens,
                    "actual_tokens": actual_tokens,
                }
            )
            continue
        if reference_labels is None:
            mismatches.append({"id": doc_id, "kind": "missing_reference_prediction"})
            continue
        if reference_labels != actual_labels:
            first = next(
                index
                for index, (reference, actual) in enumerate(zip(reference_labels, actual_labels, strict=True))
                if reference != actual
            )
            mismatches.append(
                {
                    "id": doc_id,
                    "kind": "label_mismatch",
                    "token_index": first,
                    "token": expected_tokens[first],
                    "reference_label": reference_labels[first],
                    "pipeline_label": actual_labels[first],
                }
            )
    return pipeline_pred_by_id, mismatches


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare HF runtime inference with evaluator decoded predictions.")
    parser.add_argument("--model", required=True, help="Local checkpoint directory or Hugging Face model repo.")
    parser.add_argument("--revision", default=None, help="Optional Hugging Face revision for --model.")
    parser.add_argument("--input-jsonl", required=True, help="Gold JSONL split with text/tokens/token_labels.")
    parser.add_argument("--evaluator-predictions", required=True, help="Evaluator *_predictions.jsonl reference.")
    parser.add_argument("--pipeline-dir", default="hf_model")
    parser.add_argument("--summary-json", default="")
    parser.add_argument("--mismatches-jsonl", default="")
    parser.add_argument("--max-docs", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_jsonl(Path(args.input_jsonl))
    if args.max_docs:
        rows = rows[: args.max_docs]
    reference_predictions = load_jsonl(Path(args.evaluator_predictions))
    reference_pred_by_id = prediction_labels_by_id(reference_predictions)

    AutoModelForTokenClassification, AutoTokenizer = import_runtime()
    MediaAgenciesPipeline = import_pipeline(Path(args.pipeline_dir))
    model_source, load_kwargs = resolve_model_source(args.model, revision=args.revision)
    tokenizer = AutoTokenizer.from_pretrained(model_source, **load_kwargs)
    model = AutoModelForTokenClassification.from_pretrained(model_source, **load_kwargs)
    pipeline = MediaAgenciesPipeline(model, tokenizer)

    pipeline_pred_by_id, mismatches = compare_rows(rows, reference_pred_by_id, pipeline)
    reference_metrics = metrics_for(rows, reference_pred_by_id)
    pipeline_metrics = metrics_for(rows, pipeline_pred_by_id)
    summary = {
        "model": model_source,
        "revision": args.revision if load_kwargs.get("revision") else "",
        "documents": len(rows),
        "matching_documents": len(rows) - len(mismatches),
        "mismatches": len(mismatches),
        "reference_metrics": reference_metrics,
        "pipeline_metrics": pipeline_metrics,
        "metrics_match": reference_metrics == pipeline_metrics,
        "status": "ok" if not mismatches and reference_metrics == pipeline_metrics else "mismatch",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.summary_json:
        write_json(Path(args.summary_json), summary)
    if args.mismatches_jsonl:
        path = Path(args.mismatches_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in mismatches:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
