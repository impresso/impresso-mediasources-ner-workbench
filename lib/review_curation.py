from __future__ import annotations

import argparse
import json
import os
import sys
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

RESET = "\033[0m"
GOLD_STYLE = "\033[1;32m"
PREDICTION_STYLE = "\033[1;36m"
OVERLAP_STYLE = "\033[1;35m"
CLEAR_SCREEN = "\033[2J\033[H"


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


def clear_screen() -> None:
    if sys.stdout.isatty() and os.environ.get("TERM") not in {"", "dumb"}:
        print(CLEAR_SCREEN, end="")


def latest_decisions(path: Path) -> dict[str, dict[str, Any]]:
    decisions = {}
    for row in load_jsonl(path):
        review_id = row.get("review_id")
        if review_id:
            decisions[review_id] = row
    return decisions


def pending_items(disagreements: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in disagreements if decisions.get(row["review_id"], {}).get("status", "todo") == "todo"]


def format_entity(entity: dict[str, Any] | None) -> str:
    if entity is None:
        return "<none>"
    return f"{entity['surface']} [{entity['label']}] tokens={entity['token_start']}:{entity['token_stop']}"


def token_span(entity: dict[str, Any] | None) -> tuple[int, int] | None:
    if entity is None:
        return None
    return int(entity["token_start"]), int(entity["token_stop"])


def token_marker(index: int, gold: dict[str, Any] | None, prediction: dict[str, Any] | None) -> str:
    markers = []
    for marker, entity in (("G", gold), ("P", prediction)):
        span = token_span(entity)
        if span and span[0] <= index < span[1]:
            markers.append(marker)
    return "".join(markers)


def format_token_indicator(item: dict[str, Any]) -> str:
    context = item["context"]
    start = int(context["token_start"])
    chunks = []
    for offset, token in enumerate(context["tokens"]):
        index = start + offset
        marker = token_marker(index, item.get("gold"), item.get("prediction"))
        if marker:
            chunks.append(f"[{marker}:{index}:{token}]")
        else:
            chunks.append(f"{index}:{token}")
    return " ".join(chunks)


def style_token(token: str, marker: str, *, color: bool) -> str:
    if not marker:
        return token
    wrapped = f"[{marker}:{token}]"
    if not color:
        return f"**{wrapped}**"
    style = OVERLAP_STYLE if marker == "GP" else GOLD_STYLE if marker == "G" else PREDICTION_STYLE
    return f"{style}{wrapped}{RESET}"


def format_highlighted_context(item: dict[str, Any], *, color: bool = True) -> str:
    context = item["context"]
    start = int(context["token_start"])
    chunks = []
    token_render = context.get("token_render", [])
    for offset, token in enumerate(context["tokens"]):
        index = start + offset
        marker = token_marker(index, item.get("gold"), item.get("prediction"))
        chunks.append(style_token(token, marker, color=color))
        render = token_render[offset] if offset < len(token_render) else ""
        if "NoSpaceAfter" not in render and offset != len(context["tokens"]) - 1:
            chunks.append(" ")
    return "".join(chunks)


def nearby_boundary_suggestions(
    item: dict[str, Any], *, window: int = 2, max_suggestions: int = 10
) -> list[str]:
    context = item["context"]
    context_start = int(context["token_start"])
    context_stop = int(context["token_stop"])
    tokens = context["tokens"]
    candidates: list[tuple[int, int, int, str]] = []
    seen = set()

    for name in ("gold", "prediction"):
        entity = item.get(name)
        span = token_span(entity)
        if not span:
            continue
        start, stop = span
        label = str(entity.get("label", ""))
        for left in range(max(context_start, start - window), start + 1):
            for right in range(stop, min(context_stop, stop + window) + 1):
                if left >= right:
                    continue
                key = (left, right, label)
                if key in seen:
                    continue
                seen.add(key)
                local_left = left - context_start
                local_right = right - context_start
                surface = " ".join(tokens[local_left:local_right])
                distance = abs(left - start) + abs(right - stop)
                left_expansion = max(0, start - left)
                candidates.append((distance, left_expansion, right - left, f'{left}:{right} "{surface}" label={label}'))
    return [candidate[-1] for candidate in sorted(candidates)[:max_suggestions]]


def format_choice_meaning(item: dict[str, Any]) -> list[str]:
    gold = item.get("gold")
    prediction = item.get("prediction")
    lines = [
        f"  g = accept this row's gold side: {format_entity(gold)}",
        f"  p = accept this row's prediction side: {format_entity(prediction)}",
        "  b = both displayed spans are valid mentions",
        "  n = neither displayed side is the final correct annotation; put the real correction in notes",
        "  s = skip for later; q = quit without saving this item",
    ]
    if gold is None:
        lines.append("  note: here g means keep no entity for this row; it does not select another overlapping gold span.")
    if prediction is None:
        lines.append("  note: here p means keep no prediction for this row; use notes for any corrected span.")
    if gold is None or prediction is None:
        lines.append("  partial/duplicate rows can happen when one real mention was split into several disagreement items.")
    return lines


def suggested_label(item: dict[str, Any], choice: str) -> str:
    entity = item.get(choice)
    if isinstance(entity, dict):
        return str(entity.get("label", ""))
    return ""


def print_boundary_suggestions(item: dict[str, Any]) -> None:
    suggestions = nearby_boundary_suggestions(item)
    if not suggestions:
        return
    print("boundary candidates:")
    for suggestion in suggestions:
        print(f"  {suggestion}")


def prompt_notes(item: dict[str, Any], choice: str) -> str:
    if choice in {"both", "neither"}:
        print_boundary_suggestions(item)
        return input("notes/correction required: ").strip()
    if choice in {"gold", "prediction"} and item.get(choice) is not None:
        raw = input("Press Enter to accept exactly, or type c to add a correction: ").strip().lower()
        if raw == "c":
            print_boundary_suggestions(item)
            return input("notes/correction: ").strip()
    return ""


def review_loop(items: list[dict[str, Any]], decisions_path: Path, reviewer: str, *, limit: int) -> int:
    reviewed = 0
    for index, item in enumerate(items, start=1):
        if limit and reviewed >= limit:
            break
        clear_screen()
        print("\n" + "=" * 88)
        print(f"{index}/{len(items)} {item['review_id']}")
        print(f"{item['split']} {item['language']} {item['issue_type']}")
        doc = item["document"]
        print(f"{doc['id']} {doc.get('newspaper', '')} {doc.get('date', '')}")
        print("-" * 88)
        print(format_highlighted_context(item))
        print("legend: green [G] gold, cyan [P] prediction, magenta [GP] overlap; type N for numbered tokens")
        print("-" * 88)
        print(f"gold:       {format_entity(item.get('gold'))}")
        print(f"prediction: {format_entity(item.get('prediction'))}")
        print("choice meaning:")
        for line in format_choice_meaning(item):
            print(line)
        while True:
            print("Choices: [g]old [p]rediction [b]oth [n]either [s]kip [q]uit [N]umbered tokens")
            raw = input("> ").strip()
            if raw == "N":
                print("numbered tokens:")
                print(format_token_indicator(item))
                continue
            raw = raw.lower()
            if raw == "q":
                return reviewed
            if raw not in CHOICES:
                print("Invalid choice; item not saved.")
                continue
            break
        choice = CHOICES[raw]
        correct_label = suggested_label(item, choice) if choice in {"gold", "prediction"} else ""
        notes = prompt_notes(item, choice)
        status = "ignored" if choice == "skip" else "done"
        decision = {
            "review_id": item["review_id"],
            "status": status,
            "choice": choice,
            "correct_label": correct_label,
            "notes": notes,
            "reviewer": reviewer,
            "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        append_jsonl(decisions_path, decision)
        if status == "done":
            reviewed += 1
            print(f"saved {item['review_id']}")
        else:
            print(f"ignored for this curation pass {item['review_id']}")
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
