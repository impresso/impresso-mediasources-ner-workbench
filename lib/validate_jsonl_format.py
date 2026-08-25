from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .entity_alignment import labels_to_entities


REQUIRED_FIELDS = ("id", "text", "tokens", "token_labels", "token_start_offsets", "token_end_offsets", "entities")


def load_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append((line_number, json.loads(line)))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def base_label(label: str) -> str:
    return label[2:] if label.startswith(("B-", "I-")) else label


def validate_bio_label(row_id: str, index: int, label: str) -> str | None:
    if label == "O":
        return None
    prefix, separator, entity_label = label.partition("-")
    if not separator or prefix not in {"B", "I"} or not entity_label:
        return f"{row_id}: token_labels[{index}] has invalid BIO label {label!r}"
    return None


def entity_key(entity: dict[str, Any]) -> tuple[int, int, str]:
    return (int(entity["token_start"]), int(entity["token_stop"]), str(entity["label"]))


def validate_row(row: dict[str, Any], *, line_number: int, path: Path, allow_token_label_ids: bool = False) -> list[str]:
    row_id = str(row.get("id") or f"{path}:{line_number}")
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in row:
            errors.append(f"{row_id}: missing required field {field}")
    if errors:
        return errors

    text = row.get("text")
    tokens = row.get("tokens")
    labels = row.get("token_labels")
    starts = row.get("token_start_offsets")
    stops = row.get("token_end_offsets")
    entities = row.get("entities")
    if not isinstance(text, str):
        errors.append(f"{row_id}: text is not a string")
    for field_name, value in [
        ("tokens", tokens),
        ("token_labels", labels),
        ("token_start_offsets", starts),
        ("token_end_offsets", stops),
        ("entities", entities),
    ]:
        if not isinstance(value, list):
            errors.append(f"{row_id}: {field_name} is not a list")
    if errors:
        return errors

    token_count = len(tokens)
    for field_name, value in [
        ("token_labels", labels),
        ("token_start_offsets", starts),
        ("token_end_offsets", stops),
    ]:
        if len(value) != token_count:
            errors.append(f"{row_id}: {field_name} length {len(value)} does not match tokens length {token_count}")
    if "token_label_ids" in row:
        if not allow_token_label_ids:
            errors.append(f"{row_id}: token_label_ids is present in minimal JSONL")
        elif not isinstance(row["token_label_ids"], list) or len(row["token_label_ids"]) != token_count:
            errors.append(f"{row_id}: token_label_ids length does not match tokens length {token_count}")
    if errors:
        return errors

    previous_stop = -1
    for index, (token, label, start, stop) in enumerate(zip(tokens, labels, starts, stops, strict=True)):
        if not isinstance(token, str):
            errors.append(f"{row_id}: tokens[{index}] is not a string")
            continue
        if not isinstance(label, str):
            errors.append(f"{row_id}: token_labels[{index}] is not a string")
            continue
        bio_error = validate_bio_label(row_id, index, label)
        if bio_error:
            errors.append(bio_error)
        if not isinstance(start, int) or not isinstance(stop, int):
            errors.append(f"{row_id}: offsets for token {index} are not integers")
            continue
        if start < 0 or stop < start or stop > len(text):
            errors.append(f"{row_id}: offsets for token {index} are out of bounds: {start}:{stop}")
            continue
        if start < previous_stop:
            errors.append(f"{row_id}: token offsets overlap or move backwards at token {index}: {start}:{stop}")
        previous_stop = stop
        if text[start:stop] != token:
            errors.append(f"{row_id}: token offset mismatch at token {index}: {token!r} != text[{start}:{stop}] {text[start:stop]!r}")

    entity_keys = set()
    for entity_index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            errors.append(f"{row_id}: entities[{entity_index}] is not an object")
            continue
        missing = [field for field in ("token_start", "token_stop", "label", "surface", "start", "stop") if field not in entity]
        if missing:
            errors.append(f"{row_id}: entities[{entity_index}] missing fields: {', '.join(missing)}")
            continue
        try:
            token_start = int(entity["token_start"])
            token_stop = int(entity["token_stop"])
            char_start = int(entity["start"])
            char_stop = int(entity["stop"])
        except (TypeError, ValueError):
            errors.append(f"{row_id}: entities[{entity_index}] has non-integer offsets")
            continue
        label = str(entity["label"])
        if not (0 <= token_start < token_stop <= token_count):
            errors.append(f"{row_id}: entities[{entity_index}] token span out of bounds: {token_start}:{token_stop}")
            continue
        expected_start = starts[token_start]
        expected_stop = stops[token_stop - 1]
        if (char_start, char_stop) != (expected_start, expected_stop):
            errors.append(
                f"{row_id}: entities[{entity_index}] char span {char_start}:{char_stop} "
                f"does not match token span {token_start}:{token_stop} -> {expected_start}:{expected_stop}"
            )
        if text[char_start:char_stop] != entity["surface"]:
            errors.append(f"{row_id}: entities[{entity_index}] surface mismatch")
        entity_keys.add((token_start, token_stop, label))

    bio_entities = {(start, stop, label) for start, stop, label in labels_to_entities([str(label) for label in labels])}
    if entity_keys != bio_entities:
        missing_from_entities = sorted(bio_entities - entity_keys)
        extra_entities = sorted(entity_keys - bio_entities)
        if missing_from_entities:
            errors.append(f"{row_id}: entities missing BIO spans: {missing_from_entities[:5]}")
        if extra_entities:
            errors.append(f"{row_id}: entities contain spans not present in BIO labels: {extra_entities[:5]}")
    return errors


def validate_files(paths: list[Path], *, allow_token_label_ids: bool = False, max_examples: int = 20) -> dict[str, Any]:
    summary: dict[str, Any] = {"files": {}, "errors": 0, "examples": []}
    for path in paths:
        file_errors = 0
        rows = load_jsonl(path)
        for line_number, row in rows:
            errors = validate_row(row, line_number=line_number, path=path, allow_token_label_ids=allow_token_label_ids)
            file_errors += len(errors)
            for error in errors:
                if len(summary["examples"]) < max_examples:
                    summary["examples"].append({"path": str(path), "line": line_number, "error": error})
        summary["files"][str(path)] = {"rows": len(rows), "errors": file_errors}
        summary["errors"] += file_errors
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate media-source JSONL token, offset, BIO, and entity consistency.")
    parser.add_argument("--jsonl", action="append", type=Path, required=True, help="JSONL file to validate. Can be repeated.")
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--allow-token-label-ids", action="store_true", help="Allow non-minimal token_label_ids in rows.")
    parser.add_argument("--max-examples", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = validate_files(args.jsonl, allow_token_label_ids=args.allow_token_label_ids, max_examples=args.max_examples)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if summary["errors"]:
        for example in summary["examples"]:
            print(f"{example['path']}:{example['line']}: {example['error']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
