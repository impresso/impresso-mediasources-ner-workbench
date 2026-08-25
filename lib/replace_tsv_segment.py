from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .entity_alignment import labels_to_entities


@dataclass(frozen=True)
class TsvSegment:
    tokens: tuple[str, ...]
    labels: tuple[str, ...]


def normalize_label(value: str) -> str:
    stripped = value.strip()
    if stripped in {"-", "o", "O"}:
        return "O"
    return stripped


def parse_tsv_segment(path: Path) -> TsvSegment:
    tokens: list[str] = []
    labels: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("```"):
                continue
            columns = line.split()
            if columns[:2] == ["TOKEN", "NERTAG"]:
                continue
            if len(columns) != 2:
                raise ValueError(f"{path}:{line_number}: expected TOKEN TAG columns, got {len(columns)}")
            tokens.append(columns[0])
            labels.append(normalize_label(columns[1]))
    if not tokens:
        raise ValueError(f"{path}: no TOKEN TAG rows found")
    return TsvSegment(tokens=tuple(tokens), labels=tuple(labels))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_label_map(path: Path | None) -> dict[str, int] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(label): int(label_id) for label, label_id in data.get("label2id", {}).items()}


def find_matches(row: dict[str, Any], old: TsvSegment) -> list[int]:
    tokens = [str(token) for token in row.get("tokens") or []]
    labels = [str(label) for label in row.get("token_labels") or []]
    if len(tokens) != len(labels):
        raise ValueError(f"{row.get('id')}: tokens/token_labels length mismatch")
    width = len(old.tokens)
    matches = []
    for start in range(0, len(tokens) - width + 1):
        stop = start + width
        if tuple(tokens[start:stop]) == old.tokens and tuple(labels[start:stop]) == old.labels:
            matches.append(start)
    return matches


def project_new_offsets(row: dict[str, Any], start: int, old: TsvSegment, new: TsvSegment) -> tuple[list[int], list[int]]:
    old_width = len(old.tokens)
    starts = row.get("token_start_offsets")
    stops = row.get("token_end_offsets")
    text = row.get("text")
    if not (
        isinstance(text, str)
        and isinstance(starts, list)
        and isinstance(stops, list)
        and len(starts) == len(row.get("tokens") or [])
        and len(stops) == len(row.get("tokens") or [])
    ):
        raise ValueError(f"{row.get('id')}: cannot replace tokens without complete text and token offsets")
    old_char_start = int(starts[start])
    old_char_stop = int(stops[start + old_width - 1])
    search_from = old_char_start
    new_starts: list[int] = []
    new_stops: list[int] = []
    for token in new.tokens:
        found = text.find(token, search_from, old_char_stop)
        if found < 0:
            surface = text[old_char_start:old_char_stop]
            raise ValueError(
                f"{row.get('id')}: replacement token {token!r} not found in original character span "
                f"{old_char_start}:{old_char_stop} ({surface!r})"
            )
        new_starts.append(found)
        new_stops.append(found + len(token))
        search_from = found + len(token)
    return new_starts, new_stops


def entity_family(label: str) -> str:
    if label.startswith("org.ent.pressagency."):
        return "pressagency"
    if label.startswith("org.ent.radiostation."):
        return "radiostation"
    if label.startswith("org.ent.newspaper."):
        return "newspaper"
    return "other"


def rebuild_entities(row: dict[str, Any]) -> list[dict[str, Any]]:
    tokens = row["tokens"]
    labels = [str(label) for label in row["token_labels"]]
    starts = row.get("token_start_offsets") or []
    stops = row.get("token_end_offsets") or []
    text = str(row.get("text") or "")
    entities = []
    for token_start, token_stop, label in sorted(labels_to_entities(labels)):
        char_start = int(starts[token_start]) if token_start < len(starts) else None
        char_stop = int(stops[token_stop - 1]) if token_stop - 1 < len(stops) else None
        if char_start is not None and char_stop is not None and text:
            surface = text[char_start:char_stop]
        else:
            surface = " ".join(str(token) for token in tokens[token_start:token_stop])
        entity: dict[str, Any] = {
            "entity_family": entity_family(label),
            "label": label,
            "surface": surface,
            "token_start": token_start,
            "token_stop": token_stop,
        }
        if char_start is not None and char_stop is not None:
            entity["start"] = char_start
            entity["stop"] = char_stop
        entities.append(entity)
    return entities


def replace_once(
    row: dict[str, Any],
    *,
    start: int,
    old: TsvSegment,
    new: TsvSegment,
    label2id: dict[str, int] | None = None,
) -> dict[str, Any]:
    out = dict(row)
    old_width = len(old.tokens)
    stop = start + old_width
    new_starts, new_stops = project_new_offsets(row, start, old, new)
    out["tokens"] = list(row["tokens"][:start]) + list(new.tokens) + list(row["tokens"][stop:])
    out["token_labels"] = list(row["token_labels"][:start]) + list(new.labels) + list(row["token_labels"][stop:])
    out["token_start_offsets"] = list(row["token_start_offsets"][:start]) + new_starts + list(row["token_start_offsets"][stop:])
    out["token_end_offsets"] = list(row["token_end_offsets"][:start]) + new_stops + list(row["token_end_offsets"][stop:])
    if "token_render" in out and isinstance(out["token_render"], list):
        out["token_render"] = list(row["token_render"][:start]) + [""] * len(new.tokens) + list(row["token_render"][stop:])
    if label2id is not None:
        missing = sorted({label for label in out["token_labels"] if label not in label2id})
        if missing:
            raise ValueError(f"{row.get('id')}: replacement labels missing from label map: {', '.join(missing)}")
        out["token_label_ids"] = [label2id[str(label)] for label in out["token_labels"]]
    else:
        out.pop("token_label_ids", None)
    out["entities"] = rebuild_entities(out)
    return out


def replace_segments(
    rows: list[dict[str, Any]],
    *,
    old: TsvSegment,
    new: TsvSegment,
    label2id: dict[str, int] | None = None,
    match_index: int | None = None,
    all_matches: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_locations: list[tuple[int, int]] = []
    for row_index, row in enumerate(rows):
        for start in find_matches(row, old):
            all_locations.append((row_index, start))
    if not all_locations:
        raise ValueError("old TOKEN TAG segment was not found")
    if match_index is not None:
        if match_index < 1 or match_index > len(all_locations):
            raise ValueError(f"--match-index must be between 1 and {len(all_locations)}")
        locations = [all_locations[match_index - 1]]
    elif all_matches:
        locations = all_locations
    elif len(all_locations) == 1:
        locations = all_locations
    else:
        examples = ", ".join(f"{rows[row_index].get('id')}@{start}" for row_index, start in all_locations[:10])
        raise ValueError(
            f"old TOKEN TAG segment matched {len(all_locations)} times; use --match-index N or --all-matches. "
            f"First matches: {examples}"
        )

    out_rows = [dict(row) for row in rows]
    replaced = []
    for row_index, start in sorted(locations, reverse=True):
        row = out_rows[row_index]
        out_rows[row_index] = replace_once(row, start=start, old=old, new=new, label2id=label2id)
        replaced.append({"id": str(row.get("id") or ""), "token_start": start})
    replaced.reverse()
    return out_rows, {"matches": len(all_locations), "replaced": len(replaced), "locations": replaced}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replace one TOKEN/NERTAG segment in a JSONL split with another TOKEN/NERTAG segment.")
    parser.add_argument("--input-jsonl", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--old-tsv", required=True, type=Path, help="TSV file containing the exact old TOKEN TAG block.")
    parser.add_argument("--new-tsv", required=True, type=Path, help="TSV file containing the replacement TOKEN TAG block.")
    parser.add_argument("--label-map", type=Path, help="Optional label_map.json used to regenerate token_label_ids.")
    parser.add_argument("--match-index", type=int, help="Apply only the Nth match, 1-based.")
    parser.add_argument("--all-matches", action="store_true", help="Replace every exact match of the old block.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.match_index and args.all_matches:
        raise ValueError("use either --match-index or --all-matches, not both")
    old = parse_tsv_segment(args.old_tsv)
    new = parse_tsv_segment(args.new_tsv)
    rows = load_jsonl(args.input_jsonl)
    label2id = load_label_map(args.label_map)
    out_rows, summary = replace_segments(
        rows,
        old=old,
        new=new,
        label2id=label2id,
        match_index=args.match_index,
        all_matches=args.all_matches,
    )
    write_jsonl(args.output_jsonl, out_rows)
    summary.update(
        {
            "input_jsonl": str(args.input_jsonl),
            "output_jsonl": str(args.output_jsonl),
            "old_tokens": len(old.tokens),
            "new_tokens": len(new.tokens),
        }
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
