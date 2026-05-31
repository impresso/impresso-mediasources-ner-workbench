from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Window:
    doc_index: int
    doc_id: str
    start_word: int
    tokens: list[str]
    label_ids: list[int]


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            validate_row(row, path, line_number)
            rows.append(row)
    return rows


def validate_row(row: dict[str, Any], path: str | Path, line_number: int) -> None:
    required = ["id", "tokens", "token_labels", "token_label_ids"]
    missing = [field for field in required if field not in row]
    if missing:
        raise ValueError(f"{path}:{line_number}: missing fields: {', '.join(missing)}")
    token_count = len(row["tokens"])
    for field in ["token_labels", "token_label_ids"]:
        if len(row[field]) != token_count:
            raise ValueError(f"{path}:{line_number}: {field} length does not match tokens")


def load_label_map(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "label2id" not in data or "id2label" not in data:
        raise ValueError(f"invalid label_map.json: {path}")
    if data["label2id"].get("O") != 0:
        raise ValueError("label_map.json must map O to 0")
    return data


def write_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def make_windows(
    rows: list[dict[str, Any]],
    *,
    max_words: int,
    stride_words: int,
) -> list[Window]:
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    if stride_words < 0:
        raise ValueError("stride_words must not be negative")
    step = max_words - stride_words
    if step <= 0:
        raise ValueError("stride_words must be smaller than max_words")

    windows: list[Window] = []
    for doc_index, row in enumerate(rows):
        tokens = row["tokens"]
        label_ids = row["token_label_ids"]
        if not tokens:
            continue
        start = 0
        while start < len(tokens):
            stop = min(start + max_words, len(tokens))
            windows.append(
                Window(
                    doc_index=doc_index,
                    doc_id=row["id"],
                    start_word=start,
                    tokens=tokens[start:stop],
                    label_ids=label_ids[start:stop],
                )
            )
            if stop == len(tokens):
                break
            start += step
    return windows


def strip_bio(label: str) -> str:
    if label == "O":
        return "O"
    if label.startswith("B-") or label.startswith("I-"):
        return label[2:]
    return label


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

    for i, label in enumerate(labels):
        if label == "O":
            close(i)
            continue
        prefix = label[:1] if label.startswith(("B-", "I-")) else "B"
        base = strip_bio(label)
        if prefix == "B" or start is None or active != base:
            close(i)
            start = i
            active = base
        elif prefix == "I":
            pass
    close(len(labels))
    return entities


def collect_gold_entities(row: dict[str, Any]) -> set[tuple[int, int, str]]:
    return {
        (int(entity["token_start"]), int(entity["token_stop"]), entity["label"])
        for entity in row.get("entities", [])
        if entity.get("status") == "accepted"
    }
