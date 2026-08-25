from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from . import review_ui
from .snippet_data import append_jsonl, latest_decisions, load_jsonl, write_jsonl


CLEAR_SCREEN = "\033[2J\033[H"
CHOICES = {"a": "accepted", "A": "accepted", "r": "rejected", "s": "skipped", "m": "accepted"}
FINAL_STATUSES = {"accepted", "rejected", "removed"}
SPAN_RE = re.compile(r"^(?P<start>\d+):(?P<stop>\d+)\s+(?P<label>\S+)$")
NUMBERED_TOKEN_RE = re.compile(r"(?P<index>\d+):(?P<token>\S+)")
DEFAULT_LABEL_METADATA = Path("resources/newsagency_seeds.json")
EXTRA_DEFAULT_LABEL_METADATA = [Path("resources/radiostation_seeds.json")]


def load_coverage(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    return {str(row.get("label")): row for row in rows if isinstance(row, dict) and row.get("label")}


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language") or row.get("search_language") or "unknown")


def review_labels(row: dict[str, Any]) -> set[str]:
    labels = set()
    for value in (row.get("candidate_label"), row.get("curation", {}).get("label")):
        if isinstance(value, str) and value.startswith("org.ent."):
            labels.add(value)
    for span in prediction_spans(row):
        label = span.get("label")
        if isinstance(label, str) and label.startswith("org.ent."):
            labels.add(label)
    return labels


def coverage_item(label: str, coverage: dict[str, dict[str, Any]], language: str | None = None) -> dict[str, Any]:
    row = coverage.get(label)
    if not row:
        return {}
    if language:
        languages = row.get("languages")
        if isinstance(languages, dict) and isinstance(languages.get(language), dict):
            return languages[language]
    return row


def coverage_missing(label: str, coverage: dict[str, dict[str, Any]], language: str | None = None) -> int:
    row = coverage_item(label, coverage, language)
    if not row:
        return 1
    return int(row.get("missing_to_target") or 0)


def row_needs_coverage(row: dict[str, Any], coverage: dict[str, dict[str, Any]]) -> bool:
    labels = review_labels(row)
    if not labels:
        return False
    language = row_language(row)
    return any(coverage_missing(label, coverage, language) > 0 for label in labels)


def coverage_priority(row: dict[str, Any], coverage: dict[str, dict[str, Any]]) -> tuple[int, int, int, str]:
    labels = sorted(review_labels(row))
    if not coverage or not labels:
        return (0, 0, 0, str(row.get("id", "")))
    language = row_language(row)
    missing = max(coverage_missing(label, coverage, language) for label in labels)
    items = [coverage_item(label, coverage, language) for label in labels]
    totals = [int(item.get("total") or 0) for item in items]
    pending = [int(item.get("pending_review") or 0) for item in items]
    return (-missing, min(totals or [0]), -max(pending or [0]), str(row.get("id", "")))


def clear_screen() -> None:
    review_ui.clear_screen()


def review_id(row: dict[str, Any], *, prefix: str = "newsagency-snippet") -> str:
    return f"{prefix}:{row['id']}"


def prediction_spans(row: dict[str, Any]) -> list[dict[str, Any]]:
    model = row.get("model")
    if isinstance(model, dict) and isinstance(model.get("predicted_spans"), list):
        return [span for span in model["predicted_spans"] if isinstance(span, dict)]
    return []


def span_line(span: dict[str, Any], index: int) -> str:
    confidence = span.get("confidence")
    margin = span.get("margin")
    confidence_text = f"{float(confidence):.3f}" if confidence is not None else "-"
    margin_text = f"{float(margin):.3f}" if margin is not None else "-"
    return (
        f"{index}: {span.get('token_start')}:{span.get('token_stop')} "
        f"{span.get('surface', '')} [{span.get('label', '')}] "
        f"conf={confidence_text} margin={margin_text}"
    )


def numbered_tokens(row: dict[str, Any]) -> str:
    return review_ui.numbered_tokens(row)


def load_label_metadata(path: Path) -> dict[str, dict[str, Any]]:
    return review_ui.load_label_metadata(path)


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
        print(f"  impresso article: https://impresso-project.ch/app/content-item/{article_id}")
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
        review_ui.print_mention_profile(row_info)
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
    article_id = impresso_article_id(row)
    article_url = f" https://impresso-project.ch/app/content-item/{article_id}" if article_id else ""
    print(f"{index}/{total} {review_id(row, prefix=review_prefix)}{article_url}")
    print(f"query: {row.get('query', '')}")
    print(f"candidate label: {row.get('candidate_label') or row.get('curation', {}).get('label') or ''}")
    print(f"reasons: {', '.join(row.get('curation', {}).get('reasons', []))}")
    temporal = row.get("temporal_verification")
    if isinstance(temporal, dict) and temporal.get("status") == "suspicious_before_start":
        print("TEMPORAL WARNING: document predates canonical entity start")
        print(f"  document year: {temporal.get('document_year')}")
        print(f"  entity start year: {temporal.get('start_year')}")
        if temporal.get("delta_years") is not None:
            print(f"  delta years: {temporal.get('delta_years')}")
        if temporal.get("active_period_note"):
            print(f"  active-period note: {temporal.get('active_period_note')}")
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
    print("  a = accept/review suggested spans; A = accept all suggested spans")
    print("  m = enter manual span(s)")
    print("  r = reject suggested annotation for this item; s = skip temporarily")
    print("  R = remove this sample permanently from review/export; q = quit")
    print("Choices: [a]ccept/review prediction spans [A]ccept all [m]anual span [r]eject annotation [R]emove sample [s]kip [i]nfo [N]umbered tokens [q]uit")


def target_label(row: dict[str, Any]) -> str:
    return review_ui.target_label(row)


def resolve_manual_label(raw_label: str, row: dict[str, Any], label_metadata: dict[str, dict[str, Any]] | None = None) -> str:
    return review_ui.resolve_manual_label(raw_label, row, label_metadata)


def split_trailing_manual_label(raw: str) -> tuple[str, str]:
    return review_ui.split_trailing_manual_label(raw)


def parse_numbered_token_span(
    raw: str,
    row: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> tuple[int, int, str] | None:
    return review_ui.parse_numbered_token_span(raw, row, label_metadata)


def parse_manual_span(
    raw: str,
    row: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return review_ui.parse_manual_span(raw, row, label_metadata)


def interpreted_span_line(span: dict[str, Any]) -> str:
    return review_ui.interpreted_span_line(span)


def prompt_manual_spans(
    row: dict[str, Any],
    label_metadata: dict[str, dict[str, Any]] | None = None,
    *,
    single_span: bool = False,
) -> list[dict[str, Any]] | None:
    return review_ui.prompt_manual_spans(row, label_metadata, single_span=single_span)


def prompt_prediction_spans(
    row: dict[str, Any],
    spans: list[dict[str, Any]],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if len(spans) <= 1:
        return spans[:1]

    accepted_spans = []
    print("multiple non-overlapping predicted mentions; review them one after another")
    expected_label = target_label(row)
    for span_index, span in enumerate(spans, start=1):
        print("  " + span_line(span, span_index))
        predicted_label = str(span.get("label") or "")
        if expected_label and predicted_label != expected_label:
            print(f"  this mention differs from the sampled candidate: predicted={predicted_label} candidate={expected_label}")
            print(f"  use a to keep {predicted_label}; use c only to relabel this span as {expected_label}")
        while True:
            accept_text = f"[a]ccept as {predicted_label}"
            candidate_text = f" [c]relabel as {expected_label}" if expected_label and predicted_label != expected_label else ""
            raw = input(
                f"this span: {accept_text}{candidate_text} [m]anual correction [r]eject [N]umbered tokens > "
            ).strip()
            if raw == "N":
                print(numbered_tokens(row))
                continue
            raw = raw.lower()
            if raw == "a":
                accepted_spans.append(span)
                break
            if raw == "c":
                if not expected_label or predicted_label == expected_label:
                    print("Relabeling is not available because this span already has the candidate label.")
                    continue
                accepted_spans.append({**span, "label": expected_label})
                break
            if raw == "m":
                manual_spans = prompt_manual_spans(row, label_metadata, single_span=True)
                if manual_spans is None:
                    continue
                accepted_spans.extend(manual_spans)
                break
            if raw == "r":
                break
            print("Invalid choice; span not saved.")
    return accepted_spans


def confirm_annotation_finished(
    row: dict[str, Any],
    accepted_spans: list[dict[str, Any]],
    label_metadata: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    while True:
        print("accepted annotations:")
        if accepted_spans:
            for span_index, span in enumerate(accepted_spans, start=1):
                print("  " + span_line(span, span_index))
        else:
            print("  <none>")
        raw = input("annotation finished? [Y/m] ").strip().lower()
        if raw in {"", "y", "yes"}:
            return accepted_spans
        if raw == "m":
            manual_spans = prompt_manual_spans(row, label_metadata)
            if manual_spans:
                accepted_spans.extend(manual_spans)
            continue
        print("Invalid choice; use y to save or m to add manual annotation spans.")


def review_loop(
    rows: list[dict[str, Any]],
    decisions_path: Path,
    reviewer: str,
    *,
    limit: int,
    label_metadata_path: Path = DEFAULT_LABEL_METADATA,
    input_path: Path | None = None,
    review_prefix: str = "newsagency-snippet",
    coverage_json: Path | None = None,
    only_under_target: bool = False,
    review_statuses: set[str] | None = None,
) -> int:
    decisions = latest_decisions(decisions_path)
    label_metadata = load_label_metadata(label_metadata_path)
    coverage = load_coverage(coverage_json)
    review_statuses = review_statuses or {"needs_review"}
    pending = [
        row
        for row in rows
        if row.get("curation", {}).get("status") in review_statuses
        and decisions.get(review_id(row, prefix=review_prefix), {}).get("status") not in FINAL_STATUSES
    ]
    if coverage and only_under_target:
        pending = [row for row in pending if row_needs_coverage(row, coverage)]
    if coverage:
        pending.sort(key=lambda row: coverage_priority(row, coverage))
    reviewed = 0
    for index, row in enumerate(pending, start=1):
        if limit and reviewed >= limit:
            break
        while True:
            clear_screen()
            print_review_item(row, index, len(pending), review_prefix=review_prefix)
            spans = prediction_spans(row)
            notes = ""
            while True:
                raw = input("> ").strip()
                if raw == "N":
                    print(numbered_tokens(row))
                    continue
                if raw == "A":
                    if not spans:
                        print("No predicted spans to accept.")
                        continue
                    break
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
                if raw == "n":
                    notes = input("notes: ").strip()
                    continue
                if raw == "q":
                    return reviewed
                if raw not in CHOICES:
                    print("Invalid choice; item not saved.")
                    continue
                break
            accepted_spans: list[dict[str, Any]] = []
            if raw == "a":
                target = row.get("curation", {}).get("label") or row.get("candidate_label")
                matching = [span for span in spans if span.get("label") == target]
                spans_to_review = spans if len(spans) > 1 else matching or spans
                accepted_spans = prompt_prediction_spans(row, spans_to_review, label_metadata)
                accepted_spans = confirm_annotation_finished(row, accepted_spans, label_metadata)
            elif raw == "A":
                accepted_spans = spans[:]
            elif raw == "m":
                manual_spans = prompt_manual_spans(row, label_metadata)
                if manual_spans is None:
                    continue
                accepted_spans = manual_spans
            elif raw == "remove":
                notes = input("removal reason (optional): ").strip()
            break
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
    parser.add_argument("--coverage-json", type=Path)
    parser.add_argument("--only-under-target", action="store_true")
    parser.add_argument(
        "--review-status",
        action="append",
        default=[],
        help="Curation status to review. Can be repeated. Defaults to needs_review. Use auto_accepted to audit auto-accepted rows.",
    )
    parser.add_argument("--materialize-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_jsonl(Path(args.input))
    reviewed = 0
    if not args.materialize_only:
        input_path = Path(args.input)
        review_statuses = set(args.review_status or ["needs_review"])
        reviewed = review_loop(
            rows,
            Path(args.decisions),
            args.reviewer,
            limit=args.limit,
            label_metadata_path=Path(args.label_metadata),
            input_path=input_path,
            review_prefix=args.review_prefix,
            coverage_json=args.coverage_json,
            only_under_target=args.only_under_target,
            review_statuses=review_statuses,
        )
    revised = apply_decisions(rows, Path(args.decisions), review_prefix=args.review_prefix)
    write_jsonl(Path(args.output), revised)
    print(json.dumps({"reviewed": reviewed, "rows": len(revised), "output": args.output}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
