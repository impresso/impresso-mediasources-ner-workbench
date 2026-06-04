from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .snippet_data import append_jsonl, latest_decisions, load_jsonl, write_jsonl


CLEAR_SCREEN = "\033[2J\033[H"
CHOICES = {"a": "accepted", "r": "rejected", "s": "skipped", "m": "accepted"}
FINAL_STATUSES = {"accepted", "rejected", "removed"}
SPAN_RE = re.compile(r"^(?P<start>\d+):(?P<stop>\d+)\s+(?P<label>\S+)$")
NUMBERED_TOKEN_RE = re.compile(r"(?P<index>\d+):(?P<token>\S+)")
DEFAULT_LABEL_METADATA = Path("resources/newsagency_seeds.json")


def clear_screen() -> None:
    if sys.stdout.isatty() and os.environ.get("TERM") not in {"", "dumb"}:
        print(CLEAR_SCREEN, end="")


def review_id(row: dict[str, Any], *, prefix: str = "newsagency-snippet") -> str:
    return f"{prefix}:{row['id']}"


def prediction_spans(row: dict[str, Any]) -> list[dict[str, Any]]:
    model = row.get("model")
    if isinstance(model, dict) and isinstance(model.get("predicted_spans"), list):
        return [span for span in model["predicted_spans"] if isinstance(span, dict)]
    return []


def span_line(span: dict[str, Any], index: int) -> str:
    return (
        f"{index}: {span.get('token_start')}:{span.get('token_stop')} "
        f"{span.get('surface', '')} [{span.get('label', '')}] "
        f"conf={float(span.get('confidence', 0.0)):.3f} margin={float(span.get('margin', 0.0)):.3f}"
    )


def numbered_tokens(row: dict[str, Any]) -> str:
    return " ".join(f"{index}:{token}" for index, token in enumerate(row.get("tokens", [])))


def load_label_metadata(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {str(row.get("label")): row for row in rows if row.get("label")}


def impresso_article_id(row: dict[str, Any]) -> str:
    source = row.get("source")
    if isinstance(source, dict) and source.get("document_id"):
        return str(source["document_id"])
    if row.get("source_document_id"):
        return str(row["source_document_id"])
    return str(row.get("id", "")).split("#", 1)[0]


def source_file(row: dict[str, Any]) -> str:
    if row.get("source_file"):
        return str(row["source_file"])
    source = row.get("source")
    if isinstance(source, dict) and source.get("source_file"):
        return str(source["source_file"])
    legacy = row.get("legacy")
    if isinstance(legacy, dict) and legacy.get("source_file"):
        return str(legacy["source_file"])
    return ""


def format_list(values: Any) -> str:
    if isinstance(values, list):
        return ", ".join(str(value) for value in values)
    return str(values or "")


def print_label_info(
    row: dict[str, Any],
    label_metadata_path: Path,
    label_metadata: dict[str, dict[str, Any]],
    *,
    input_path: Path | None = None,
) -> None:
    article_id = impresso_article_id(row)
    label = row.get("candidate_label") or row.get("curation", {}).get("label") or ""
    labels = [str(label)] if label else []
    for span in prediction_spans(row):
        span_label = str(span.get("label", ""))
        if span_label and span_label not in labels:
            labels.append(span_label)

    print("info")
    if input_path:
        print(f"  input file: {input_path}")
    print(f"  metadata file: {label_metadata_path}")
    source_path = source_file(row)
    if source_path:
        print(f"  source file: {source_path}")
    if article_id:
        print(f"  impresso article: https://impresso-project.ch/app/article/{article_id}")
    for current_label in labels:
        row_info = label_metadata.get(current_label)
        print(f"  label: {current_label}")
        if not row_info:
            print("    <no local metadata found>")
            continue
        print(f"    name: {row_info.get('display_name', '')}")
        active = row_info.get("active_period") or {}
        if active:
            start = active.get("start") or "?"
            end = active.get("end") or "present/unknown"
            print(f"    active: {start} - {end}; {active.get('note', '')}")
        if row_info.get("description"):
            print(f"    description: {row_info['description']}")
        if row_info.get("annotation_note"):
            print(f"    annotation note: {row_info['annotation_note']}")
        aliases_by_language = row_info.get("aliases_by_language") or {}
        for lang in ("de", "fr", "en"):
            if aliases_by_language.get(lang):
                print(f"    aliases {lang}: {format_list(aliases_by_language[lang])}")
        contextual_aliases = row_info.get("contextual_aliases") or []
        if contextual_aliases:
            print("    contextual aliases:")
            for alias in contextual_aliases:
                print(f"      - {alias.get('alias', '')}: {alias.get('note', '')}")
        sources = row_info.get("metadata_sources") or []
        if sources:
            print("    sources:")
            for source in sources:
                print(f"      - {source.get('type', 'source')}: {source.get('url', '')}")


def print_review_item(row: dict[str, Any], index: int, total: int, *, review_prefix: str = "newsagency-snippet") -> None:
    print("\n" + "=" * 88)
    print(f"{index}/{total} {review_id(row, prefix=review_prefix)}")
    print(f"query: {row.get('query', '')}")
    print(f"candidate label: {row.get('candidate_label') or row.get('curation', {}).get('label') or ''}")
    print(f"reasons: {', '.join(row.get('curation', {}).get('reasons', []))}")
    print("-" * 88)
    print(row.get("text", ""))
    print("-" * 88)
    spans = prediction_spans(row)
    if spans:
        print("predicted spans:")
        for span_index, span in enumerate(spans, start=1):
            print("  " + span_line(span, span_index))
    else:
        print("predicted spans: <none>")
    print("choice meaning:")
    print("  a = accept/review suggested spans; m = enter manual span(s)")
    print("  r = reject suggested annotation for this item; s = skip temporarily")
    print("  R = remove this sample permanently from review/export; q = quit")
    print("Choices: [a]ccept/review prediction spans [m]anual span [r]eject annotation [R]emove sample [s]kip [i]nfo [N]umbered tokens [q]uit")


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("curation", {}).get("label") or row.get("candidate_label") or "")


def parse_numbered_token_span(raw: str, row: dict[str, Any]) -> tuple[int, int, str] | None:
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
    label = target_label(row)
    if not label:
        raise ValueError("cannot infer label; use: 12:13 org.ent.radiostation.bbc")
    return indexes[0], indexes[-1] + 1, label


def parse_manual_span(raw: str, row: dict[str, Any]) -> dict[str, Any]:
    match = SPAN_RE.match(raw.strip())
    if match:
        start = int(match.group("start"))
        stop = int(match.group("stop"))
        label = match.group("label")
    else:
        parsed = parse_numbered_token_span(raw, row)
        if parsed is None:
            raise ValueError('expected: 12:13 org.ent.pressagency.reuters or pasted tokens like 9:B 10:. 11:B')
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


def prompt_manual_spans(row: dict[str, Any]) -> list[dict[str, Any]]:
    accepted_spans = []
    print("numbered tokens:")
    print(numbered_tokens(row))
    print('manual correction syntax: 12:13 org.ent.pressagency.reuters')
    print('or paste numbered tokens, e.g. 9:B 10:. 11:B 12:. 13:C 14:.')
    while True:
        try:
            accepted_spans.append(parse_manual_span(input("span> "), row))
        except ValueError as exc:
            print(exc)
            continue
        raw = input("add another span? [y/N] ").strip().lower()
        if raw not in {"y", "yes"}:
            return accepted_spans


def prompt_prediction_spans(row: dict[str, Any], spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(spans) <= 1:
        return spans[:1]

    accepted_spans = []
    print("multiple predicted spans; review them one after another")
    for span_index, span in enumerate(spans, start=1):
        print("  " + span_line(span, span_index))
        while True:
            raw = input("this span: [a]ccept [m]anual correction [r]eject [N]umbered tokens > ").strip()
            if raw == "N":
                print(numbered_tokens(row))
                continue
            raw = raw.lower()
            if raw == "a":
                accepted_spans.append(span)
                break
            if raw == "m":
                accepted_spans.extend(prompt_manual_spans(row))
                break
            if raw == "r":
                break
            print("Invalid choice; span not saved.")
    return accepted_spans


def review_loop(
    rows: list[dict[str, Any]],
    decisions_path: Path,
    reviewer: str,
    *,
    limit: int,
    label_metadata_path: Path = DEFAULT_LABEL_METADATA,
    input_path: Path | None = None,
    review_prefix: str = "newsagency-snippet",
) -> int:
    decisions = latest_decisions(decisions_path)
    label_metadata = load_label_metadata(label_metadata_path)
    pending = [
        row
        for row in rows
        if row.get("curation", {}).get("status") == "needs_review"
        and decisions.get(review_id(row, prefix=review_prefix), {}).get("status") not in FINAL_STATUSES
    ]
    reviewed = 0
    for index, row in enumerate(pending, start=1):
        if limit and reviewed >= limit:
            break
        clear_screen()
        print_review_item(row, index, len(pending), review_prefix=review_prefix)
        spans = prediction_spans(row)
        while True:
            raw = input("> ").strip()
            if raw == "N":
                print(numbered_tokens(row))
                continue
            if raw == "R":
                raw = "remove"
                break
            if raw.lower() == "i":
                print_label_info(row, label_metadata_path, label_metadata, input_path=input_path)
                input("press Enter to return to curation > ")
                clear_screen()
                print_review_item(row, index, len(pending), review_prefix=review_prefix)
                continue
            raw = raw.lower()
            if raw == "q":
                return reviewed
            if raw not in CHOICES:
                print("Invalid choice; item not saved.")
                continue
            break
        accepted_spans: list[dict[str, Any]] = []
        notes = ""
        if raw == "a":
            target = row.get("curation", {}).get("label") or row.get("candidate_label")
            matching = [span for span in spans if span.get("label") == target]
            spans_to_review = spans if len(spans) > 1 else matching or spans
            accepted_spans = prompt_prediction_spans(row, spans_to_review)
            if len(accepted_spans) > 1:
                notes = input("notes for accepted spans (optional): ").strip()
        elif raw == "m":
            accepted_spans = prompt_manual_spans(row)
            notes = input("notes (optional): ").strip()
        elif raw in {"r", "s"}:
            notes = input("notes (optional): ").strip()
        elif raw == "remove":
            notes = input("removal reason (optional): ").strip()
        status = "removed" if raw == "remove" else CHOICES[raw]
        decision = {
            "review_id": review_id(row, prefix=review_prefix),
            "candidate_id": row["id"],
            "status": status,
            "accepted_spans": accepted_spans,
            "reviewer": reviewer,
            "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "notes": notes,
        }
        append_jsonl(decisions_path, decision)
        reviewed += 1
        print(f"saved {review_id(row, prefix=review_prefix)}: {status}")
    return reviewed


def apply_decisions(rows: list[dict[str, Any]], decisions_path: Path, *, review_prefix: str = "newsagency-snippet") -> list[dict[str, Any]]:
    decisions = latest_decisions(decisions_path)
    out = []
    for row in rows:
        revised = dict(row)
        decision = decisions.get(review_id(row, prefix=review_prefix))
        if decision:
            revised["curation"] = {
                **revised.get("curation", {}),
                "status": decision["status"],
                "reviewer": decision.get("reviewer"),
                "reviewed_at": decision.get("reviewed_at"),
                "notes": decision.get("notes"),
            }
            if decision.get("accepted_spans"):
                revised["accepted_spans"] = decision["accepted_spans"]
        out.append(revised)
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review news-agency snippets that the model marked as uncertain.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--label-metadata", default=str(DEFAULT_LABEL_METADATA))
    parser.add_argument("--review-prefix", default="newsagency-snippet")
    parser.add_argument("--materialize-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_jsonl(Path(args.input))
    reviewed = 0
    if not args.materialize_only:
        input_path = Path(args.input)
        reviewed = review_loop(
            rows,
            Path(args.decisions),
            args.reviewer,
            limit=args.limit,
            label_metadata_path=Path(args.label_metadata),
            input_path=input_path,
            review_prefix=args.review_prefix,
        )
    revised = apply_decisions(rows, Path(args.decisions), review_prefix=args.review_prefix)
    write_jsonl(Path(args.output), revised)
    print(json.dumps({"reviewed": reviewed, "rows": len(revised), "output": args.output}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
