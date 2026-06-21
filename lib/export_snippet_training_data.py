from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .snippet_data import candidate_tokens, load_jsonl, strip_html, tokenize_with_offsets, write_jsonl


ACCEPTED_STATUSES = {"auto_accepted", "accepted"}
NEGATIVE_STATUSES = {"rejected"}
LABEL_ALIASES = {
    "org.ent.pressagency.reuter": "org.ent.pressagency.reuters",
}


def load_label_map(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "label2id" not in data:
        raise ValueError(f"{path}: missing label2id")
    return data


def extend_label_map(label_map: dict[str, Any], metadata_paths: list[Path]) -> dict[str, Any]:
    label2id = dict(label_map["label2id"])
    for path in metadata_paths:
        if not path.is_file():
            continue
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


def canonical_label(label: Any) -> str:
    value = str(label or "")
    return LABEL_ALIASES.get(value, value)


def canonicalize_span_labels(row_id: str, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for span in spans:
        label = canonical_label(span.get("label"))
        if label != span.get("label"):
            print(f"{row_id}: canonicalized snippet label {span.get('label')} -> {label}")
        out.append({**span, "label": label})
    return out


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


def normalized_span_for_export(
    row_id: str,
    span: dict[str, Any],
    *,
    text: str,
    starts: list[int],
    stops: list[int],
) -> dict[str, Any] | None:
    try:
        token_start = int(span["token_start"])
        token_stop = int(span["token_stop"])
    except (KeyError, TypeError, ValueError):
        return None
    if 0 <= token_start < token_stop <= len(starts):
        token_char_start = starts[token_start]
        token_char_stop = stops[token_stop - 1]
        if "start" not in span or "stop" not in span:
            return {**span, "start": token_char_start, "stop": token_char_stop, "token_start": token_start, "token_stop": token_stop}
    try:
        char_start = int(span["start"])
        char_stop = int(span["stop"])
    except (KeyError, TypeError, ValueError):
        return None
    if char_start < 0 or char_stop <= char_start or char_stop > len(text):
        return normalized_span_from_surface(row_id, span, text=text, starts=starts, stops=stops)
    if 0 <= token_start < token_stop <= len(starts):
        if token_char_start == char_start and token_char_stop == char_stop:
            return {**span, "start": char_start, "stop": char_stop, "token_start": token_start, "token_stop": token_stop}
    try:
        repaired_token_start = starts.index(char_start)
        repaired_token_stop = stops.index(char_stop) + 1
    except ValueError:
        return normalized_span_from_surface(row_id, span, text=text, starts=starts, stops=stops)
    if repaired_token_start >= repaired_token_stop:
        return normalized_span_from_surface(row_id, span, text=text, starts=starts, stops=stops)
    print(f"{row_id}: repaired stale token offsets for span {char_start}:{char_stop} {span.get('label', '')}")
    return {**span, "start": char_start, "stop": char_stop, "token_start": repaired_token_start, "token_stop": repaired_token_stop}


def normalized_span_from_surface(
    row_id: str,
    span: dict[str, Any],
    *,
    text: str,
    starts: list[int],
    stops: list[int],
) -> dict[str, Any] | None:
    surface = str(span.get("surface") or "")
    if not surface:
        return None
    matches = []
    search_from = 0
    while True:
        start = text.find(surface, search_from)
        if start < 0:
            break
        stop = start + len(surface)
        matches.append((start, stop))
        search_from = start + max(1, len(surface))
    if len(matches) != 1:
        return None
    start, stop = matches[0]
    try:
        token_start = starts.index(start)
        token_stop = stops.index(stop) + 1
    except ValueError:
        return None
    if token_start >= token_stop:
        return None
    print(f"{row_id}: relocated stale span by surface to {start}:{stop} {span.get('label', '')}")
    return {**span, "start": start, "stop": stop, "token_start": token_start, "token_stop": token_stop}


def valid_spans_for_export(row: dict[str, Any], spans: list[dict[str, Any]], *, text: str, starts: list[int], stops: list[int]) -> list[dict[str, Any]]:
    row_id = str(row.get("id") or row.get("document_id") or "")
    valid = []
    seen = set()
    invalid = 0
    for span in spans:
        normalized = normalized_span_for_export(row_id, span, text=text, starts=starts, stops=stops)
        if normalized is None:
            invalid += 1
            continue
        key = (int(normalized["token_start"]), int(normalized["token_stop"]), str(normalized["label"]))
        if key in seen:
            continue
        seen.add(key)
        valid.append(normalized)
    if invalid:
        print(f"{row_id}: ignored {invalid} stale/out-of-window accepted span(s) during snippet export")
    if spans and not valid:
        raise ValueError(f"{row_id}: accepted snippet has no valid spans in the exported text window")
    return valid


def span_is_exactly_in_window(span: dict[str, Any], *, text: str, starts: list[int], stops: list[int]) -> bool:
    try:
        start = int(span["start"])
        stop = int(span["stop"])
        token_start = int(span["token_start"])
        token_stop = int(span["token_stop"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        0 <= start < stop <= len(text)
        and 0 <= token_start < token_stop <= len(starts)
        and starts[token_start] == start
        and stops[token_stop - 1] == stop
    )


def patch_window_for_accepted_spans(
    row: dict[str, Any],
    spans: list[dict[str, Any]],
    *,
    text: str,
    tokens: list[str],
    starts: list[int],
    stops: list[int],
) -> tuple[str, list[str], list[int], list[int], list[dict[str, Any]]]:
    if not spans:
        return text, tokens, starts, stops, spans
    patched_text = text
    patched_spans = [dict(span) for span in spans]
    used_fragments: set[int] = set()
    represented = {
        (str(span.get("label") or ""), str(span.get("surface") or ""))
        for span in patched_spans
        if span_is_exactly_in_window(span, text=text, starts=starts, stops=stops)
    }
    matches = row.get("matches")
    match_fragments = [strip_html(str(match)).strip() for match in matches] if isinstance(matches, list) else []

    for index, span in enumerate(patched_spans):
        surface = str(span.get("surface") or "")
        label = str(span.get("label") or "")
        if not surface or span_is_exactly_in_window(span, text=patched_text, starts=starts, stops=stops):
            continue
        if (label, surface) not in represented and surface in patched_text:
            represented.add((label, surface))
            continue
        fragment_index = next(
            (
                idx
                for idx, fragment in enumerate(match_fragments)
                if idx not in used_fragments and surface in fragment and fragment not in patched_text
            ),
            None,
        )
        if fragment_index is None:
            continue
        fragment = match_fragments[fragment_index]
        used_fragments.add(fragment_index)
        separator = "\n...\n"
        offset = len(patched_text) + len(separator)
        local_start = fragment.find(surface)
        patched_text = f"{patched_text}{separator}{fragment}"
        patched_spans[index] = {
            **span,
            "start": offset + local_start,
            "stop": offset + local_start + len(surface),
        }
        represented.add((label, surface))
        print(f"{row.get('id')}: expanded export window to include accepted span {surface!r}")

    tokens, starts, stops = tokenize_with_offsets(patched_text)
    return patched_text, tokens, starts, stops, patched_spans


def labels_to_entities(labels: list[str], starts: list[int], stops: list[int], text: str) -> list[dict[str, Any]]:
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
                "entity_family": "radiostation" if active.startswith("org.ent.radiostation.") else "pressagency",
                "label": active,
                "token_start": start,
                "token_stop": stop,
                "start": char_start,
                "stop": char_stop,
                "surface": text[char_start:char_stop],
                "status": "accepted",
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
        status = str(curation.get("status") or "")
        if status not in ACCEPTED_STATUSES | NEGATIVE_STATUSES:
            continue
        spans = selected_spans(row)
        if not spans and status in ACCEPTED_STATUSES:
            continue
        spans = canonicalize_span_labels(str(row.get("id") or row.get("document_id") or ""), spans)
        text, tokens, starts, stops = candidate_tokens(row)
        text, tokens, starts, stops, spans = patch_window_for_accepted_spans(row, spans, text=text, tokens=tokens, starts=starts, stops=stops)
        spans = valid_spans_for_export(row, spans, text=text, starts=starts, stops=stops)
        if not spans and status in ACCEPTED_STATUSES:
            continue
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
                "entities": labels_to_entities(labels, starts, stops, text),
                "quality_flags": ["reviewed_negative_snippet"] if not spans else [],
                "split_group": split_group,
                "legacy": {
                    "source_format": "sampled-snippet-jsonl",
                    "source_id": source_id,
                    "source_document_id": source_document_id,
                    "source_issue_id": split_group,
                    "query": row.get("query", ""),
                    "review_status": str((row.get("curation") or {}).get("status") or ""),
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
