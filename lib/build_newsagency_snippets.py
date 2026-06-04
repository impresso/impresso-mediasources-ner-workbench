from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .snippet_data import load_jsonl, write_jsonl


def snippet_from_tokens(row: dict[str, Any], entity: dict[str, Any], *, radius: int) -> dict[str, Any]:
    tokens = row["tokens"]
    token_start = int(entity["token_start"])
    token_stop = int(entity["token_stop"])
    left = max(0, token_start - radius)
    right = min(len(tokens), token_stop + radius)
    char_start = row["token_start_offsets"][left]
    char_stop = row["token_end_offsets"][right - 1]
    snippet = row["text"][char_start:char_stop]
    local_token_starts = [int(offset) - char_start for offset in row["token_start_offsets"][left:right]]
    local_token_stops = [int(offset) - char_start for offset in row["token_end_offsets"][left:right]]
    local_entity_start = token_start - left
    local_entity_stop = token_stop - left
    source_id = row["id"]
    label = entity["label"]
    return {
        "id": f"{source_id}#snippet-{token_start}-{token_stop}",
        "source_document_id": source_id,
        "entity_family": "pressagency",
        "candidate_label": label,
        "query": entity.get("normalized_surface") or entity.get("surface") or label.rsplit(".", 1)[-1],
        "language": row.get("language", ""),
        "date": row.get("date", ""),
        "mediaId": row.get("newspaper", ""),
        "snippet": snippet,
        "text": snippet,
        "tokens": tokens[left:right],
        "token_start_offsets": local_token_starts,
        "token_end_offsets": local_token_stops,
        "seed_span": {
            "token_start": local_entity_start,
            "token_stop": local_entity_stop,
            "label": label,
            "surface": entity.get("surface", ""),
        },
        "source": {
            "type": "legacy_jsonl_entity_context",
            "split": row.get("split", ""),
            "document_id": source_id,
            "source_file": row.get("source_file", ""),
            "token_start": token_start,
            "token_stop": token_stop,
        },
        "curation": {
            "status": "todo",
            "label": label,
            "notes": None,
        },
    }


def build_snippets(input_paths: list[Path], *, radius: int, labels: set[str] | None, limit: int) -> list[dict[str, Any]]:
    rows = []
    for path in input_paths:
        for row in load_jsonl(path):
            for entity in row.get("entities", []):
                label = str(entity.get("label", ""))
                if not label.startswith("org.ent.pressagency."):
                    continue
                if labels is not None and label not in labels:
                    continue
                rows.append(snippet_from_tokens(row, entity, radius=radius))
                if limit and len(rows) >= limit:
                    return rows
    return rows


def parse_labels(raw: str) -> set[str] | None:
    labels = {item.strip() for item in raw.split() if item.strip()}
    return labels or None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build news-agency snippet candidates from legacy JSONL entity contexts.")
    parser.add_argument("--input", action="append", required=True, help="Input legacy JSONL file. Can be repeated.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--context-radius", type=int, default=24)
    parser.add_argument("--labels", default="", help="Optional whitespace-separated canonical labels to keep.")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = build_snippets(
        [Path(path) for path in args.input],
        radius=args.context_radius,
        labels=parse_labels(args.labels),
        limit=args.limit,
    )
    write_jsonl(Path(args.output), rows)
    print(json.dumps({"rows": len(rows), "output": args.output}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
