from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .snippet_data import candidate_tokens, load_jsonl, write_jsonl


ACCEPTED_STATUSES = {"auto_accepted", "accepted"}


def load_label_map(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "label2id" not in data:
        raise ValueError(f"{path}: missing label2id")
    return data


def extend_label_map(label_map: dict[str, Any], metadata_paths: list[Path]) -> dict[str, Any]:
    label2id = dict(label_map["label2id"])
    for path in metadata_paths:
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            label = str(row.get("label", ""))
            if not label.startswith("org.ent."):
                continue
            for tag in (f"B-{label}", f"I-{label}"):
                if tag not in label2id:
                    label2id[tag] = len(label2id)
    return {
        **label_map,
        "label2id": label2id,
        "id2label": {str(index): label for label, index in label2id.items()},
    }


def selected_spans(row: dict[str, Any]) -> list[dict[str, Any]]:
    manual = row.get("accepted_spans")
    if isinstance(manual, list):
        return [span for span in manual if isinstance(span, dict)]
    model = row.get("model")
    if isinstance(model, dict) and isinstance(model.get("predicted_spans"), list):
        target = row.get("curation", {}).get("label") or row.get("candidate_label")
        spans = [span for span in model["predicted_spans"] if isinstance(span, dict)]
        if target:
            matching = [span for span in spans if span.get("label") == target]
            return matching or spans
        return spans
    return []


def empty_labels(token_count: int) -> list[str]:
    return ["O"] * token_count


def apply_span(labels: list[str], span: dict[str, Any]) -> None:
    start = int(span["token_start"])
    stop = int(span["token_stop"])
    label = str(span["label"])
    if start < 0 or stop <= start or stop > len(labels):
        raise ValueError(f"invalid span: {span}")
    for index in range(start, stop):
        labels[index] = f"{'B' if index == start else 'I'}-{label}"


def labels_to_entities(row_id: str, labels: list[str], tokens: list[str], starts: list[int], stops: list[int], text: str) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    start: int | None = None
    active = ""

    def close(stop: int) -> None:
        nonlocal start, active
        if start is None:
            return
        char_start = starts[start]
        char_stop = stops[stop - 1]
        entities.append(
            {
                "entity_id": f"{row_id}#ent-{len(entities)}",
                "entity_family": "radiostation" if active.startswith("org.ent.radiostation.") else "pressagency",
                "label": active,
                "token_start": start,
                "token_stop": stop,
                "start": char_start,
                "stop": char_stop,
                "surface": text[char_start:char_stop],
                "normalized_surface": " ".join(tokens[start:stop]),
                "has_ocr_correction": False,
                "max_ocr_levenshtein": 0.0,
            }
        )
        start = None
        active = ""

    for index, label in enumerate(labels):
        if label == "O":
            close(index)
            continue
        base = label[2:] if label.startswith(("B-", "I-")) else label
        prefix = label[:1] if label.startswith(("B-", "I-")) else "B"
        if prefix == "B" or start is None or active != base:
            close(index)
            start = index
            active = base
    close(len(labels))
    return entities


def source_component(row: dict[str, Any]) -> str:
    value = row.get("source_component")
    if value:
        return str(value)
    status = row.get("curation", {}).get("status")
    if status == "auto_accepted":
        return "newsagency_snippet_auto"
    family = row.get("entity_family")
    if family == "radiostation":
        return "radiostation_snippet_manual"
    return "newsagency_snippet_manual"


def export_rows(input_path: Path, label_map_path: Path, *, extra_label_metadata: list[Path] | None = None) -> list[dict[str, Any]]:
    label_map = load_label_map(label_map_path)
    if extra_label_metadata:
        label_map = extend_label_map(label_map, extra_label_metadata)
    label2id = label_map["label2id"]
    exported = []
    for row in load_jsonl(input_path):
        curation = row.get("curation", {})
        if curation.get("status") not in ACCEPTED_STATUSES:
            continue
        text, tokens, starts, stops = candidate_tokens(row)
        labels = empty_labels(len(tokens))
        spans = selected_spans(row)
        if not spans:
            continue
        for span in spans:
            apply_span(labels, span)
        unknown = sorted(set(labels) - set(label2id))
        if unknown:
            raise ValueError(f"{row.get('id')}: labels missing from label map: {unknown}")
        row_id = str(row["id"])
        exported.append(
            {
                "schema_version": "mediaagencies-jsonl-v0.1",
                "id": row_id,
                "document_id": row_id,
                "split": "train",
                "language": row.get("language") or row.get("search_language") or "",
                "newspaper": row.get("newspaper") or row.get("mediaId") or "",
                "date": row.get("date", ""),
                "year": int(str(row["date"])[:4]) if str(row.get("date", ""))[:4].isdigit() else None,
                "text": text,
                "tokens": tokens,
                "token_start_offsets": starts,
                "token_end_offsets": stops,
                "token_labels": labels,
                "token_label_ids": [int(label2id[label]) for label in labels],
                "entities": labels_to_entities(row_id, labels, tokens, starts, stops, text),
                "quality_flags": [],
                "source_component": source_component(row),
                "legacy": {
                    "source_format": "sampled-snippet-jsonl",
                    "source_id": row.get("id", row_id),
                    "query": row.get("query", ""),
                },
            }
        )
    return exported


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export accepted snippet curation rows into training JSONL.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label-map", required=True)
    parser.add_argument("--extra-label-metadata", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = export_rows(Path(args.input), Path(args.label_map), extra_label_metadata=[Path(path) for path in args.extra_label_metadata])
    write_jsonl(Path(args.output), rows)
    print(json.dumps({"rows": len(rows), "output": args.output}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
