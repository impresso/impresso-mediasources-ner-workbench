from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


TOKEN_RE = re.compile(r"\w+(?:[-']\w+)*|[^\w\s]", re.UNICODE)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.is_file():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def row_text(row: dict[str, Any]) -> str:
    for field in ("text", "snippet"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    matches = row.get("matches")
    if isinstance(matches, list) and matches:
        return " ... ".join(str(item).strip() for item in matches if str(item).strip())
    raise ValueError(f"candidate row {row.get('id', '<missing-id>')}: missing text/snippet/matches")


def tokenize_with_offsets(text: str) -> tuple[list[str], list[int], list[int]]:
    tokens: list[str] = []
    starts: list[int] = []
    stops: list[int] = []
    for match in TOKEN_RE.finditer(text):
        tokens.append(match.group(0))
        starts.append(match.start())
        stops.append(match.end())
    return tokens, starts, stops


def candidate_tokens(row: dict[str, Any]) -> tuple[str, list[str], list[int], list[int]]:
    text = row_text(row)
    tokens = row.get("tokens")
    starts = row.get("token_start_offsets")
    stops = row.get("token_end_offsets")
    if (
        isinstance(tokens, list)
        and isinstance(starts, list)
        and isinstance(stops, list)
        and len(tokens) == len(starts) == len(stops)
    ):
        return text, [str(token) for token in tokens], [int(start) for start in starts], [int(stop) for stop in stops]
    tokens, starts, stops = tokenize_with_offsets(text)
    return text, tokens, starts, stops


def candidate_id(row: dict[str, Any], index: int) -> str:
    for field in ("id", "uid", "content_item_id", "ci_id"):
        value = row.get(field)
        if value:
            return str(value)
    return f"candidate-{index:06d}"


def latest_decisions(path: Path) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        review_id = row.get("review_id")
        if review_id:
            decisions[str(review_id)] = row
    return decisions
