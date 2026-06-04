from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .snippet_data import append_jsonl, candidate_id, latest_decisions, load_jsonl, row_text, write_jsonl


CLEAR_SCREEN = "\033[2J\033[H"
CHOICES = {"y": "yes", "n": "no", "s": "skip"}


def clear_screen() -> None:
    if sys.stdout.isatty() and os.environ.get("TERM") not in {"", "dumb"}:
        print(CLEAR_SCREEN, end="")


def review_id(row: dict[str, Any], index: int) -> str:
    return f"radiostation-snippet:{candidate_id(row, index)}"


def pending_rows(rows: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> list[tuple[int, dict[str, Any], str]]:
    out = []
    for index, row in enumerate(rows, start=1):
        rid = review_id(row, index)
        if decisions.get(rid, {}).get("status") not in {"yes", "no", "skip"}:
            out.append((index, row, rid))
    return out


def print_item(row: dict[str, Any], rid: str, current: int, total: int) -> None:
    print("\n" + "=" * 88)
    print(f"{current}/{total} {rid}")
    print(f"query: {row.get('query', '')}")
    print(f"language: {row.get('language') or row.get('search_language') or ''}")
    print(f"date: {row.get('date', '')}")
    print(f"media: {row.get('newspaper') or row.get('mediaId') or ''}")
    print("-" * 88)
    print(row_text(row))
    print("-" * 88)
    print("Choices: [y]es radio station mention [n]o [s]kip/unsure [q]uit")


def review_loop(rows: list[dict[str, Any]], decisions_path: Path, reviewer: str, *, limit: int) -> int:
    decisions = latest_decisions(decisions_path)
    pending = pending_rows(rows, decisions)
    reviewed = 0
    for position, (index, row, rid) in enumerate(pending, start=1):
        if limit and reviewed >= limit:
            break
        clear_screen()
        print_item(row, rid, position, len(pending))
        while True:
            raw = input("> ").strip().lower()
            if raw == "q":
                return reviewed
            if raw not in CHOICES:
                print("Invalid choice; item not saved.")
                continue
            break
        notes = ""
        if CHOICES[raw] in {"yes", "skip"}:
            notes = input("notes (optional): ").strip()
        decision = {
            "review_id": rid,
            "candidate_id": candidate_id(row, index),
            "status": CHOICES[raw],
            "reviewer": reviewer,
            "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "notes": notes,
        }
        append_jsonl(decisions_path, decision)
        reviewed += 1
        print(f"saved {rid}: {CHOICES[raw]}")
    return reviewed


def materialize_views(rows: list[dict[str, Any]], decisions_path: Path, output_dir: Path) -> dict[str, int]:
    decisions = latest_decisions(decisions_path)
    grouped: dict[str, list[dict[str, Any]]] = {"yes": [], "no": [], "skip": []}
    for index, row in enumerate(rows, start=1):
        rid = review_id(row, index)
        decision = decisions.get(rid)
        if not decision:
            continue
        status = decision.get("status")
        if status not in grouped:
            continue
        out = dict(row)
        out["id"] = candidate_id(row, index)
        out["curation"] = {
            "status": status,
            "reviewer": decision.get("reviewer", ""),
            "reviewed_at": decision.get("reviewed_at", ""),
            "notes": decision.get("notes", ""),
        }
        grouped[status].append(out)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "positive_snippets.jsonl", grouped["yes"])
    write_jsonl(output_dir / "negative_snippets.jsonl", grouped["no"])
    write_jsonl(output_dir / "skipped_snippets.jsonl", grouped["skip"])
    return {status: len(items) for status, items in grouped.items()}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Triage sampled radio-station snippets.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--materialize-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_jsonl(Path(args.input))
    reviewed = 0
    if not args.materialize_only:
        reviewed = review_loop(rows, Path(args.decisions), args.reviewer, limit=args.limit)
    counts = materialize_views(rows, Path(args.decisions), Path(args.output_dir))
    print(json.dumps({"reviewed": reviewed, "views": counts}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
