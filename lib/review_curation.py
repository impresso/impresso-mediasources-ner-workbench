from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from . import review_ui


CHOICES = {
    "g": "gold",
    "p": "prediction",
    "b": "both",
    "m": "manual",
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
        "  m = enter manual annotation span(s)",
        "  n = neither displayed side is a valid mention",
        "  s = skip for later; q = quit without saving this item",
    ]
    if gold is None:
        lines.append("  note: here g means keep no entity for this row; it does not select another overlapping gold span.")
    if prediction is None:
        lines.append("  note: here p means keep no prediction for this row; use m for any corrected span.")
    if gold is None or prediction is None:
        lines.append("  partial/duplicate rows can happen when one real mention was split into several disagreement items.")
    return lines


def suggested_label(item: dict[str, Any], choice: str) -> str:
    entity = item.get(choice)
    if isinstance(entity, dict):
        return str(entity.get("label", ""))
    return ""


def target_label(item: dict[str, Any]) -> str:
    for key in ("prediction", "gold"):
        entity = item.get(key)
        if isinstance(entity, dict) and entity.get("label"):
            return str(entity["label"])
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
        return input("notes required: ").strip()
    if choice in {"gold", "prediction"} and item.get(choice) is not None:
        raw = input("Press Enter to accept exactly, or type c to add a correction: ").strip().lower()
        if raw == "c":
            print_boundary_suggestions(item)
            return input("notes/correction: ").strip()
    return ""


def context_surface(item: dict[str, Any], start: int, stop: int) -> str:
    context = item["context"]
    context_start = int(context["token_start"])
    context_stop = int(context["token_stop"])
    if start < context_start or stop > context_stop or start >= stop:
        raise ValueError(f"manual span must be inside displayed context {context_start}:{context_stop}")
    local_start = start - context_start
    local_stop = stop - context_start
    context_text = context.get("text")
    if isinstance(context_text, str) and context_text:
        return " ".join(str(token) for token in context["tokens"][local_start:local_stop])
    return " ".join(str(token) for token in context["tokens"][local_start:local_stop])


def parse_manual_curation_span(
    raw: str,
    item: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw = raw.strip()
    body, raw_label = review_ui.split_trailing_manual_label(raw)
    body = body or raw
    context = item["context"]
    context_start = int(context["token_start"])
    context_stop = int(context["token_stop"])
    tokens = context["tokens"]

    displayed = review_ui.parse_displayed_span(raw, {"candidate_label": target_label(item)}, label_metadata)
    if displayed is not None:
        start, stop, label = displayed
    else:
        match = review_ui.SPAN_RE.match(raw)
        if match:
            start = int(match.group("start"))
            stop = int(match.group("stop"))
            label = review_ui.resolve_manual_label(match.group("label") or "", {"candidate_label": target_label(item)}, label_metadata)
        else:
            matches = list(review_ui.NUMBERED_TOKEN_RE.finditer(body))
            if not matches:
                raise ValueError('expected: 1522:1523 ats-sda or pasted tokens like 1522:HnviiH ats-sda')
            indexes = [int(match.group("index")) for match in matches]
            expected = list(range(indexes[0], indexes[-1] + 1))
            if indexes != expected:
                raise ValueError("pasted numbered tokens must be contiguous")
            for match in matches:
                index = int(match.group("index"))
                if index < context_start or index >= context_stop:
                    raise ValueError(f"token span out of displayed context {context_start}:{context_stop}")
                pasted = match.group("token")
                current = str(tokens[index - context_start])
                if pasted != current:
                    raise ValueError(f"pasted token {index}:{pasted} does not match current token {index}:{current}")
            start = indexes[0]
            stop = indexes[-1] + 1
            label = review_ui.resolve_manual_label(raw_label, {"candidate_label": target_label(item)}, label_metadata)
    if start < context_start or stop > context_stop or start >= stop:
        raise ValueError(f"manual span must be inside displayed context {context_start}:{context_stop}")
    return {
        "token_start": start,
        "token_stop": stop,
        "label": label,
        "surface": context_surface(item, start, stop),
    }


def interpreted_manual_span_line(span: dict[str, Any]) -> str:
    return f"interpreted: {span['token_start']}:{span['token_stop']} \"{span['surface']}\" [{span['label']}]"


def prompt_manual_spans(item: dict[str, Any]) -> list[dict[str, Any]] | None:
    label_metadata = review_ui.load_label_metadata()
    accepted_spans: list[dict[str, Any]] = []
    print("numbered tokens:")
    print(format_token_indicator(item))
    print('manual correction syntax: 1522:1523 ats-sda or 1522:1523 org.ent.pressagency.ats-sda')
    print('or paste numbered tokens, e.g. 1522:HnviiH ats-sda')
    print('if no label is supplied, the displayed prediction/gold label is used when available')
    print('manual commands: N = show numbered tokens, q = cancel/finish manual entry')
    while True:
        raw_span = input("span> ").strip()
        if raw_span == "N":
            print("numbered tokens:")
            print(format_token_indicator(item))
            continue
        if raw_span.lower() in {"q", "quit", "done"}:
            return accepted_spans or None
        try:
            span = parse_manual_curation_span(raw_span, item, label_metadata)
        except ValueError as exc:
            print(exc)
            continue
        accepted_spans.append(span)
        print(interpreted_manual_span_line(span))
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
            print("Choices: [g]old [p]rediction [b]oth [m]anual [n]either [s]kip [q]uit [N]umbered tokens")
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
        accepted_spans: list[dict[str, Any]] = []
        notes = ""
        if choice == "manual":
            manual_spans = prompt_manual_spans(item)
            if manual_spans is None:
                continue
            accepted_spans = manual_spans
            correct_label = accepted_spans[0]["label"] if len(accepted_spans) == 1 else ""
        else:
            notes = prompt_notes(item, choice)
        status = "ignored" if choice == "skip" else "done"
        decision = {
            "review_id": item["review_id"],
            "status": status,
            "choice": choice,
            "correct_label": correct_label,
            "accepted_spans": accepted_spans,
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
