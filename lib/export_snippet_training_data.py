from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
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


def base_document_id(value: Any) -> str:
    return str(value or "").split("#", 1)[0]


def sample_issue_id(value: Any) -> str:
    document_id = base_document_id(value)
    if "-i" in document_id:
        return document_id.rsplit("-i", 1)[0]
    return document_id


def source_split_group(row: dict[str, Any]) -> str:
    if row.get("sample_issue_id"):
        return str(row["sample_issue_id"])
    if row.get("sample_document_id"):
        return sample_issue_id(row["sample_document_id"])
    source = row.get("source")
    if isinstance(source, dict) and source.get("document_id"):
        return sample_issue_id(source["document_id"])
    return sample_issue_id(row.get("id"))


def stable_digest(value: str, seed: int) -> str:
    return hashlib.sha1(f"{seed}\t{value}".encode("utf-8")).hexdigest()


def split_group_assignments(rows: list[dict[str, Any]], *, test_fraction: float, validation_fraction: float, seed: int) -> dict[str, str]:
    if test_fraction < 0 or validation_fraction < 0 or test_fraction + validation_fraction >= 1:
        raise ValueError("split fractions must be non-negative and sum to less than 1")
    groups = sorted({str(row["split_group"]) for row in rows}, key=lambda group: stable_digest(group, seed))
    if not groups:
        return {}
    if len(groups) == 1:
        return {groups[0]: "train"}
    test_count = math.ceil(len(groups) * test_fraction) if test_fraction else 0
    validation_count = math.ceil(len(groups) * validation_fraction) if validation_fraction else 0
    if test_fraction and len(groups) > 1:
        test_count = max(1, min(test_count, len(groups) - validation_count))
    remaining_after_test = len(groups) - test_count
    if validation_fraction and remaining_after_test > 1:
        validation_count = max(1, min(validation_count, remaining_after_test - 1))
    assignments = {group: "train" for group in groups}
    for group in groups[:test_count]:
        assignments[group] = "test"
    for group in groups[test_count : test_count + validation_count]:
        assignments[group] = "validation"
    return assignments


def apply_split_assignments(rows: list[dict[str, Any]], *, test_fraction: float, validation_fraction: float, seed: int) -> list[dict[str, Any]]:
    assignments = split_group_assignments(rows, test_fraction=test_fraction, validation_fraction=validation_fraction, seed=seed)
    out = []
    for row in rows:
        split = assignments.get(str(row["split_group"]), "train")
        out.append({**row, "split": split})
    return out


def unique_row_id(base_id: str, text: str, spans: list[dict[str, Any]], id_counts: Counter[str]) -> str:
    if id_counts[base_id] <= 1:
        return base_id
    payload = json.dumps(
        {
            "id": base_id,
            "text": text,
            "spans": [
                {
                    "label": span.get("label"),
                    "start": span.get("start"),
                    "stop": span.get("stop"),
                    "token_start": span.get("token_start"),
                    "token_stop": span.get("token_stop"),
                }
                for span in spans
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return f"{base_id}#snippet-{digest}"


def export_rows(input_path: Path, label_map_path: Path, *, extra_label_metadata: list[Path] | None = None) -> list[dict[str, Any]]:
    label_map = load_label_map(label_map_path)
    if extra_label_metadata:
        label_map = extend_label_map(label_map, extra_label_metadata)
    label2id = label_map["label2id"]
    prepared = []
    for row in load_jsonl(input_path):
        curation = row.get("curation", {})
        if curation.get("status") not in ACCEPTED_STATUSES:
            continue
        spans = selected_spans(row)
        if not spans:
            continue
        text, tokens, starts, stops = candidate_tokens(row)
        prepared.append((row, spans, text, tokens, starts, stops))
    id_counts = Counter(str(row["id"]) for row, *_ in prepared)
    exported = []
    for row, spans, text, tokens, starts, stops in prepared:
        labels = empty_labels(len(tokens))
        for span in spans:
            apply_span(labels, span)
        unknown = sorted(set(labels) - set(label2id))
        if unknown:
            raise ValueError(f"{row.get('id')}: labels missing from label map: {unknown}")
        source_id = str(row["id"])
        row_id = unique_row_id(source_id, text, spans, id_counts)
        split_group = source_split_group(row)
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        source_document_id = row.get("sample_document_id") or source.get("document_id") or ""
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
                "split_group": split_group,
                "legacy": {
                    "source_format": "sampled-snippet-jsonl",
                    "source_id": source_id,
                    "source_document_id": source_document_id,
                    "source_issue_id": split_group,
                    "query": row.get("query", ""),
                },
            }
        )
    return exported


def write_split_outputs(rows: list[dict[str, Any]], *, output: Path, validation_output: Path | None, test_output: Path | None) -> dict[str, int]:
    paths = {"train": output, "validation": validation_output, "test": test_output}
    counts: dict[str, int] = {}
    for split, path in paths.items():
        if path is None:
            continue
        split_rows = sorted(
            ({key: value for key, value in row.items() if key != "split_group"} for row in rows if row.get("split") == split),
            key=lambda row: (str(row.get("document_id") or row.get("id") or "").casefold(), str(row.get("document_id") or row.get("id") or "")),
        )
        write_jsonl(path, split_rows)
        counts[split] = len(split_rows)
    return counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export accepted snippet curation rows into training JSONL.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--validation-output")
    parser.add_argument("--test-output")
    parser.add_argument("--validation-fraction", type=float, default=0.0)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--label-map", required=True)
    parser.add_argument("--extra-label-metadata", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = export_rows(Path(args.input), Path(args.label_map), extra_label_metadata=[Path(path) for path in args.extra_label_metadata])
    test_fraction = args.test_fraction if args.test_output else 0.0
    validation_fraction = args.validation_fraction if args.validation_output else 0.0
    rows = apply_split_assignments(rows, test_fraction=test_fraction, validation_fraction=validation_fraction, seed=args.split_seed)
    counts = write_split_outputs(
        rows,
        output=Path(args.output),
        validation_output=Path(args.validation_output) if args.validation_output else None,
        test_output=Path(args.test_output) if args.test_output else None,
    )
    print(json.dumps({"rows": len(rows), "outputs": counts}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
