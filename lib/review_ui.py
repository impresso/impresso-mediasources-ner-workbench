from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable


CLEAR_SCREEN = "\033[2J\033[H"
SPAN_RE = re.compile(r"^(?P<start>\d+):(?P<stop>\d+)(?:\s+(?P<label>\S+))?$")
DISPLAYED_SPAN_RE = re.compile(
    r"^\s*(?:(?:\d+):\s+)?(?P<start>\d+):(?P<stop>\d+)"
    r"(?:\s+(?P<surface>.*?))?\s+\[(?P<label>org\.ent\.[^\]\s]+)\]"
)
NUMBERED_TOKEN_RE = re.compile(r"(?P<index>\d+):(?P<token>\S+)")
DEFAULT_LABEL_METADATA = Path("resources/newsagency_seeds.json")
EXTRA_DEFAULT_LABEL_METADATA = [Path("resources/radiostation_seeds.json")]
NUMBERED_TOKEN_LIMIT = 513


def clear_screen() -> None:
    if sys.stdout.isatty() and os.environ.get("TERM") not in {"", "dumb"}:
        print(CLEAR_SCREEN, end="")


def load_label_metadata(path: Path | Iterable[Path] = DEFAULT_LABEL_METADATA) -> dict[str, dict[str, Any]]:
    if isinstance(path, Path):
        paths = [path, DEFAULT_LABEL_METADATA, *EXTRA_DEFAULT_LABEL_METADATA]
    else:
        paths = [*path, DEFAULT_LABEL_METADATA, *EXTRA_DEFAULT_LABEL_METADATA]
    metadata: dict[str, dict[str, Any]] = {}
    for current_path in paths:
        if not current_path.is_file():
            continue
        rows = json.loads(current_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "")
            if label and label not in metadata:
                metadata[label] = row
    return metadata


def format_list(values: Any) -> str:
    if isinstance(values, list):
        return ", ".join(str(value) for value in values)
    return str(values or "")


def print_mention_profile(row_info: dict[str, Any]) -> None:
    profile = row_info.get("mention_profile")
    if not isinstance(profile, dict) or not profile:
        return
    print("    mention profile:")
    if profile.get("typical_surfaces"):
        print(f"      typical surfaces: {format_list(profile['typical_surfaces'])}")
    if profile.get("span_guidance"):
        print(f"      span guidance: {profile['span_guidance']}")
    if profile.get("include_generic_terms"):
        print(f"      include generic terms: {profile['include_generic_terms']}")
    if profile.get("exclude_patterns"):
        print(f"      exclude patterns: {format_list(profile['exclude_patterns'])}")
    if profile.get("notes"):
        print(f"      notes: {profile['notes']}")


def target_label(row: dict[str, Any]) -> str:
    return str(
        row.get("curation", {}).get("label")
        or row.get("candidate_label")
        or row.get("target_label")
        or row.get("suggested_label")
        or ""
    )


def resolve_manual_label(
    raw_label: str,
    row: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> str:
    label = raw_label.strip()
    strict_catalog = bool(label_metadata)
    label_metadata = label_metadata or {}
    if not label:
        inferred = target_label(row)
        if inferred:
            if strict_catalog and inferred not in label_metadata:
                raise ValueError(
                    f"unknown entity label {inferred}; it is not present in the loaded entity catalogs"
                )
            return inferred
        raise ValueError("cannot infer label; add a full label or canonical id, e.g. agence-radio")
    if label.startswith(("org.ent.pressagency.", "org.ent.radiostation.", "org.ent.newspaper.")):
        if strict_catalog and label not in label_metadata:
            raise ValueError(
                f"unknown entity label {label}; it is not present in the loaded entity catalogs"
            )
        return label
    matches = []
    for metadata_label, metadata_row in label_metadata.items():
        canonical_id = str(metadata_row.get("canonical_id") or metadata_label.rsplit(".", 1)[-1])
        if label == canonical_id or label == metadata_label.rsplit(".", 1)[-1]:
            matches.append(metadata_label)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"ambiguous canonical id {label}; use the full label")
    if strict_catalog:
        raise ValueError(
            f"unknown entity label {label}; use a canonical id or full label from the loaded entity catalogs"
        )
    target = target_label(row)
    if target.startswith(("org.ent.pressagency.", "org.ent.radiostation.", "org.ent.newspaper.")):
        family = ".".join(target.split(".")[:3])
        return f"{family}.{label}"
    raise ValueError(f"unknown canonical id {label}; use the full label")


def focus_token_span(row: dict[str, Any]) -> tuple[int, int] | None:
    if row.get("token_start") is None or row.get("token_stop") is None:
        return None
    return int(row["token_start"]), int(row["token_stop"])


def token_window(total: int, focus: tuple[int, int] | None, limit: int) -> tuple[int, int]:
    if total <= limit or limit <= 0:
        return 0, total
    if focus is None:
        return 0, min(total, limit)
    focus_start, focus_stop = focus
    focus_mid = max(0, min(total, (focus_start + focus_stop) // 2))
    start = max(0, focus_mid - limit // 2)
    stop = min(total, start + limit)
    start = max(0, stop - limit)
    return start, stop


def numbered_tokens(
    row: dict[str, Any],
    *,
    marker_span: tuple[int, int] | None = None,
    max_tokens: int = NUMBERED_TOKEN_LIMIT,
) -> str:
    tokens = row.get("tokens") or []
    start, stop = token_window(len(tokens), focus_token_span(row) or marker_span, max_tokens)
    chunks = []
    if start > 0:
        chunks.append(f"... {start} earlier tokens omitted ...")
    for index in range(start, stop):
        token = tokens[index]
        value = f"{index}:{token}"
        if marker_span is not None and marker_span[0] <= index < marker_span[1]:
            value = f"[P:{value}]"
        chunks.append(value)
    if stop < len(tokens):
        chunks.append(f"... {len(tokens) - stop} later tokens omitted ...")
    return " ".join(chunks)


def split_trailing_manual_label(raw: str) -> tuple[str, str]:
    stripped = raw.strip()
    if not stripped:
        return "", ""
    parts = stripped.rsplit(maxsplit=1)
    if len(parts) == 1:
        return stripped, ""
    body, possible_label = parts
    if ":" not in possible_label:
        return body, possible_label
    return stripped, ""


def parse_numbered_token_span(
    raw: str,
    row: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> tuple[int, int, str] | None:
    body, raw_label = split_trailing_manual_label(raw)
    raw = body or raw
    matches = list(NUMBERED_TOKEN_RE.finditer(raw.strip()))
    if not matches:
        return None
    indexes = [int(match.group("index")) for match in matches]
    expected = list(range(indexes[0], indexes[-1] + 1))
    if indexes != expected:
        raise ValueError("pasted numbered tokens must be contiguous")
    tokens = row["tokens"]
    for match in matches:
        index = int(match.group("index"))
        if index < 0 or index >= len(tokens):
            raise ValueError("token span out of range")
        pasted = match.group("token")
        if pasted != str(tokens[index]):
            raise ValueError(f"pasted token {index}:{pasted} does not match current token {index}:{tokens[index]}")
    label = resolve_manual_label(raw_label, row, label_metadata)
    return indexes[0], indexes[-1] + 1, label


def parse_displayed_span(
    raw: str,
    row: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> tuple[int, int, str] | None:
    match = DISPLAYED_SPAN_RE.match(raw.strip())
    if not match:
        return None
    start = int(match.group("start"))
    stop = int(match.group("stop"))
    label = resolve_manual_label(match.group("label"), row, label_metadata)
    return start, stop, label


def parse_manual_span(
    raw: str,
    row: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    match = SPAN_RE.match(raw.strip())
    if match:
        start = int(match.group("start"))
        stop = int(match.group("stop"))
        label = resolve_manual_label(match.group("label") or "", row, label_metadata)
    else:
        parsed = parse_displayed_span(raw, row, label_metadata)
        if parsed is None:
            parsed = parse_numbered_token_span(raw, row, label_metadata)
        if parsed is None:
            raise ValueError('expected: 12:13 reuters, 12:13 Surface [org.ent...], or pasted tokens like 9:B 10:. 11:B bbc')
        start, stop, label = parsed
    tokens = row["tokens"]
    starts = row["token_start_offsets"]
    stops = row["token_end_offsets"]
    text = row["text"]
    if start < 0 or stop <= start or stop > len(tokens):
        raise ValueError("token span out of range")
    return {
        "token_start": start,
        "token_stop": stop,
        "label": label,
        "surface": text[starts[start] : stops[stop - 1]],
        "start": starts[start],
        "stop": stops[stop - 1],
        "confidence": None,
        "margin": None,
    }


def interpreted_span_line(span: dict[str, Any]) -> str:
    return (
        f"interpreted: {span['token_start']}:{span['token_stop']} "
        f"\"{span['surface']}\" [{span['label']}]"
    )


def prompt_manual_spans(
    row: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
    *,
    single_span: bool = False,
) -> list[dict[str, Any]] | None:
    accepted_spans = []
    print("numbered tokens:")
    print("-" * 88)
    print(numbered_tokens(row))
    print("-" * 88)
    print('manual correction syntax: 12:13 reuters or 12:13 org.ent.pressagency.reuters')
    print('or paste numbered tokens, e.g. 9:B 10:. 11:B 12:. 13:C 14:. bbc')
    print('if no label is supplied, the current candidate label is used')
    if single_span:
        print('manual commands: N = show numbered tokens, q = cancel this manual correction')
    else:
        print('manual commands: N = show numbered tokens, q = finish manual entry')
    while True:
        raw_span = input("span> ").strip()
        if raw_span == "N":
            print("numbered tokens:")
            print("-" * 88)
            print(numbered_tokens(row))
            print("-" * 88)
            continue
        if raw_span.lower() in {"q", "quit", "done"}:
            return accepted_spans or None
        try:
            span = parse_manual_span(raw_span, row, label_metadata)
        except ValueError as exc:
            print(exc)
            continue
        accepted_spans.append(span)
        print(interpreted_span_line(span))
        if single_span:
            return accepted_spans
        while True:
            raw = input("finished? [Y/n/v] ").strip().lower()
            if raw in {"", "y", "yes"}:
                return accepted_spans
            if raw in {"n", "no"}:
                break
            if raw in {"v", "revise"}:
                accepted_spans.pop()
                print("removed last manual span; enter the revised span")
                break
            print("Invalid choice; use y to finish, n to add another span, or v to revise.")
