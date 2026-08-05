from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .audit_empty_training_docs import labels_to_entities, row_id, write_json, write_jsonl, write_tsv
from .score_radiostation_snippets import (
    attach_offsets,
    find_alias_spans,
    find_contextual_source_formula_spans,
    high_precision_press_aliases,
    seed_aliases,
)
from .score_newsagency_snippets import (
    suppress_contained_same_label_spans,
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_label_metadata(paths: list[Path]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.is_file():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "")
            if label:
                metadata[label] = row
    return metadata


def token_to_char_span(row: dict[str, Any], token_start: int, token_stop: int) -> tuple[int, int] | None:
    starts = row.get("token_start_offsets") or []
    stops = row.get("token_end_offsets") or []
    if token_start < 0 or token_stop <= token_start or token_stop > len(stops) or token_start >= len(starts):
        return None
    return int(starts[token_start]), int(stops[token_stop - 1])


def overlaps_existing(row: dict[str, Any], start: int, stop: int) -> bool:
    for entity in row.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        entity_start = entity.get("start")
        entity_stop = entity.get("stop")
        if entity_start is None or entity_stop is None:
            span = token_to_char_span(row, int(entity.get("token_start", -1)), int(entity.get("token_stop", -1)))
            if span is None:
                continue
            entity_start, entity_stop = span
        if start < int(entity_stop) and stop > int(entity_start):
            return True
    return False


def surface_for(row: dict[str, Any], start: int, stop: int, token_start: int, token_stop: int) -> str:
    text = str(row.get("text") or "")
    if 0 <= start <= stop <= len(text):
        return text[start:stop]
    return " ".join(str(token) for token in (row.get("tokens") or [])[token_start:token_stop])


def model_prediction_spans(row: dict[str, Any], prediction: dict[str, Any] | None, target_label: str) -> list[dict[str, Any]]:
    if not prediction:
        return []
    labels = [str(label) for label in prediction.get("pred_labels", [])]
    spans: list[dict[str, Any]] = []
    for token_start, token_stop, label in labels_to_entities(labels):
        if label != target_label:
            continue
        char_span = token_to_char_span(row, token_start, token_stop)
        if char_span is None:
            continue
        start, stop = char_span
        spans.append(
            {
                "label": label,
                "matcher": "model_prediction",
                "source": "model",
                "start": start,
                "stop": stop,
                "surface": surface_for(row, start, stop, token_start, token_stop),
                "token_start": token_start,
                "token_stop": token_stop,
            }
        )
    return spans


def pattern_spans(row: dict[str, Any], seed: dict[str, Any], target_label: str) -> list[dict[str, Any]]:
    tokens = [str(token) for token in row.get("tokens") or []]
    starts = [int(value) for value in row.get("token_start_offsets") or []]
    stops = [int(value) for value in row.get("token_end_offsets") or []]
    text = str(row.get("text") or "")
    if not tokens or len(starts) != len(tokens) or len(stops) != len(tokens):
        return []
    if target_label.startswith("org.ent.pressagency."):
        token_spans = find_alias_spans(tokens, high_precision_press_aliases(seed), target_label)
        token_spans.extend(find_contextual_source_formula_spans(tokens, seed, target_label))
    else:
        token_spans = find_alias_spans(tokens, seed_aliases(seed), target_label)
    spans = attach_offsets(suppress_contained_same_label_spans(token_spans), starts, stops, text)
    for span in spans:
        span["source"] = "pattern"
        span.setdefault("matcher", "alias")
    return spans


def merge_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[int, int, str], dict[str, Any]] = {}
    for span in spans:
        key = (int(span["start"]), int(span["stop"]), str(span["label"]))
        if key not in merged:
            merged[key] = dict(span)
            merged[key]["sources"] = [str(span.get("source") or span.get("matcher") or "unknown")]
            continue
        sources = merged[key].setdefault("sources", [])
        source = str(span.get("source") or span.get("matcher") or "unknown")
        if source not in sources:
            sources.append(source)
    return sorted(merged.values(), key=lambda row: (int(row["start"]), int(row["stop"]), str(row["label"])))


def candidate_context(text: str, start: int, stop: int, radius: int = 80) -> tuple[str, str]:
    return text[max(0, start - radius) : start].strip(), text[stop : min(len(text), stop + radius)].strip()


def build_candidates(
    *,
    input_jsonl: Path,
    target_label: str,
    metadata_paths: list[Path],
    audit_id: str,
    predictions_jsonl: Path | None = None,
    split: str = "",
    use_patterns: bool = True,
    use_model: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not target_label:
        raise ValueError("target_label is required")
    metadata = load_label_metadata(metadata_paths)
    seed = metadata.get(target_label)
    if seed is None and use_patterns:
        raise ValueError(f"target label not found in metadata: {target_label}")
    rows = load_jsonl(input_jsonl)
    predictions = {row_id(row): row for row in load_jsonl(predictions_jsonl)} if predictions_jsonl and predictions_jsonl.is_file() else {}
    candidates: list[dict[str, Any]] = []
    tsv_rows: list[dict[str, Any]] = []
    by_language: dict[str, int] = {}
    by_source: dict[str, int] = {}

    for row in rows:
        doc_id = row_id(row)
        spans: list[dict[str, Any]] = []
        if use_patterns and seed is not None:
            spans.extend(pattern_spans(row, seed, target_label))
        if use_model:
            spans.extend(model_prediction_spans(row, predictions.get(doc_id), target_label))
        missing_spans = []
        for span in merge_spans(spans):
            start = int(span["start"])
            stop = int(span["stop"])
            if overlaps_existing(row, start, stop):
                continue
            left, right = candidate_context(str(row.get("text") or ""), start, stop)
            item = {
                "label": target_label,
                "left_context": left,
                "matcher": span.get("matcher", ""),
                "right_context": right,
                "source": ",".join(span.get("sources") or [str(span.get("source") or "")]),
                "start": start,
                "stop": stop,
                "surface": span.get("surface") or surface_for(row, start, stop, int(span["token_start"]), int(span["token_stop"])),
                "token_start": span.get("token_start"),
                "token_stop": span.get("token_stop"),
            }
            missing_spans.append(item)
            for source in str(item["source"]).split(","):
                if source:
                    by_source[source] = by_source.get(source, 0) + 1
            tsv_rows.append(
                {
                    "document_id": doc_id,
                    "split": split,
                    "language": row.get("language", ""),
                    "date": row.get("date", ""),
                    "newspaper": row.get("newspaper", ""),
                    "label": target_label,
                    "surface": item["surface"],
                    "start": start,
                    "stop": stop,
                    "token_start": item.get("token_start", ""),
                    "token_stop": item.get("token_stop", ""),
                    "source": item["source"],
                    "matcher": item["matcher"],
                    "left_context": item["left_context"],
                    "right_context": item["right_context"],
                }
            )
        if not missing_spans:
            continue
        language = str(row.get("language") or "")
        by_language[language] = by_language.get(language, 0) + len(missing_spans)
        candidates.append(
            {
                "audit_id": audit_id,
                "audit_mode": "missing-span",
                "audit_split": split,
                "candidate_spans": missing_spans,
                "date": row.get("date", ""),
                "document_id": doc_id,
                "language": row.get("language", ""),
                "newspaper": row.get("newspaper", ""),
                "target_label": target_label,
                "text": row.get("text", ""),
                "token_end_offsets": row.get("token_end_offsets", []),
                "token_start_offsets": row.get("token_start_offsets", []),
                "tokens": row.get("tokens", []),
            }
        )
    candidates.sort(key=lambda row: str(row["document_id"]))
    tsv_rows.sort(key=lambda row: (str(row["document_id"]), int(row["start"]), int(row["stop"])))
    summary = {
        "audit_id": audit_id,
        "audit_mode": "missing-span",
        "input_jsonl": str(input_jsonl),
        "predictions_jsonl": str(predictions_jsonl or ""),
        "split": split,
        "target_label": target_label,
        "documents": len(rows),
        "candidate_documents": len(candidates),
        "candidate_spans": len(tsv_rows),
        "candidate_spans_by_language": dict(sorted(by_language.items())),
        "candidate_spans_by_source": dict(sorted(by_source.items())),
        "use_model": use_model,
        "use_patterns": use_patterns,
    }
    return candidates, tsv_rows, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build target-specific missing-span audit candidates for an existing JSONL split.")
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--predictions-jsonl", default="")
    parser.add_argument("--target-label", required=True)
    parser.add_argument("--label-metadata", action="append", type=Path, default=[])
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--split", default="")
    parser.add_argument("--candidates-jsonl", required=True)
    parser.add_argument("--candidates-tsv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--no-model", action="store_true")
    parser.add_argument("--no-patterns", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates, tsv_rows, summary = build_candidates(
        input_jsonl=Path(args.input_jsonl),
        target_label=args.target_label,
        metadata_paths=args.label_metadata or [Path("resources/newsagency_seeds.json"), Path("resources/radiostation_seeds.json")],
        audit_id=args.audit_id,
        predictions_jsonl=Path(args.predictions_jsonl) if args.predictions_jsonl else None,
        split=args.split,
        use_model=not args.no_model,
        use_patterns=not args.no_patterns,
    )
    write_jsonl(Path(args.candidates_jsonl), candidates)
    write_tsv(
        Path(args.candidates_tsv),
        tsv_rows,
        [
            "document_id",
            "split",
            "language",
            "date",
            "newspaper",
            "label",
            "surface",
            "start",
            "stop",
            "token_start",
            "token_stop",
            "source",
            "matcher",
            "left_context",
            "right_context",
        ],
    )
    write_json(Path(args.summary_json), summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
