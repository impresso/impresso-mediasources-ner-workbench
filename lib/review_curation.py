from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


CHOICES = {
    "g": "gold",
    "p": "prediction",
    "b": "both",
    "n": "neither",
    "s": "skip",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def latest_decisions(path: Path) -> dict[str, dict[str, Any]]:
    decisions = {}
    for row in load_jsonl(path):
        review_id = row.get("review_id")
        if review_id:
            decisions[review_id] = row
    return decisions


def pending_items(disagreements: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in disagreements if decisions.get(row["review_id"], {}).get("status") != "done"]


def format_entity(entity: dict[str, Any] | None) -> str:
    if entity is None:
        return "<none>"
    return f"{entity['surface']} [{entity['label']}] tokens={entity['token_start']}:{entity['token_stop']}"


def suggested_label(item: dict[str, Any], choice: str) -> str:
    entity = item.get(choice)
    if isinstance(entity, dict):
        return str(entity.get("label", ""))
    return ""


def review_loop(items: list[dict[str, Any]], decisions_path: Path, reviewer: str, *, limit: int) -> int:
    reviewed = 0
    for index, item in enumerate(items, start=1):
        if limit and reviewed >= limit:
            break
        print("\n" + "=" * 88)
        print(f"{index}/{len(items)} {item['review_id']}")
        print(f"{item['split']} {item['language']} {item['issue_type']}")
        doc = item["document"]
        print(f"{doc['id']} {doc.get('newspaper', '')} {doc.get('date', '')}")
        print("-" * 88)
        print(item["context"]["text"])
        print("-" * 88)
        print(f"gold:       {format_entity(item.get('gold'))}")
        print(f"prediction: {format_entity(item.get('prediction'))}")
        print("Choices: [g]old [p]rediction [b]oth [n]either [s]kip [q]uit")
        raw = input("> ").strip().lower()
        if raw == "q":
            break
        if raw not in CHOICES:
            print("Invalid choice; item not saved.")
            continue
        choice = CHOICES[raw]
        correct_label = suggested_label(item, choice) if choice in {"gold", "prediction"} else ""
        notes = input("notes: ").strip()
        decision = {
            "review_id": item["review_id"],
            "status": "done",
            "choice": choice,
            "correct_label": correct_label,
            "notes": notes,
            "reviewer": reviewer,
            "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        append_jsonl(decisions_path, decision)
        reviewed += 1
        print(f"saved {item['review_id']}")
    return reviewed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Terminal reviewer for curation disagreement JSONL.")
    parser.add_argument("--disagreements", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    disagreements = load_jsonl(Path(args.disagreements))
    decisions = latest_decisions(Path(args.decisions))
    items = pending_items(disagreements, decisions)
    print(f"pending: {len(items)} / total: {len(disagreements)}")
    reviewed = review_loop(items, Path(args.decisions), args.reviewer, limit=args.limit)
    print(f"reviewed: {reviewed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
