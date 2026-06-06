from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from . import review_ui


CLEAR_SCREEN = "\033[2J\033[H"
VERIFIED_STATUS = "verified"
RESET = "\033[0m"
SUGGESTION_STYLE = "\033[1;36m"
SPAN_RE = re.compile(r"^(?P<start>\d+):(?P<stop>\d+)\s+(?P<label>\S+)$")
TOKEN_RE = re.compile(r"\S+")
DEFAULT_LABEL_METADATA = [Path("resources/newsagency_seeds.json"), Path("resources/radiostation_seeds.json")]
CONTEXT_RADIUS = 240


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def latest_decisions(path: Path) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        review_id = row.get("review_id")
        if review_id:
            decisions[str(review_id)] = row
    return decisions


def is_verified(decision: dict[str, Any] | None) -> bool:
    return bool(decision) and (decision.get("audit_status") == VERIFIED_STATUS or decision.get("status") == "done")


def stable_review_id(audit_id: str, document_id: str, start: int, stop: int, label: str) -> str:
    payload = f"{audit_id}\t{document_id}\t{start}\t{stop}\t{label}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"span-patch:{audit_id}:{digest}"


def load_label_metadata(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.is_file():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "")
            if label and label not in metadata:
                metadata[label] = row
    return metadata


def span_patch(
    *,
    audit_id: str,
    candidate: dict[str, Any],
    entity: dict[str, Any],
    source_path: str,
    source_index: int,
) -> dict[str, Any]:
    document_id = str(candidate.get("document_id") or candidate.get("id") or "")
    start = int(entity["start"])
    stop = int(entity["stop"])
    label = str(entity["label"])
    surface = str(entity.get("surface", ""))
    left_context = str(entity.get("left_context", ""))
    right_context = str(entity.get("right_context", ""))
    summary = f'{document_id}: "{surface}" -> {label}'
    return {
        "audit_id": audit_id,
        "date": candidate.get("date", ""),
        "document_id": document_id,
        "language": candidate.get("language", ""),
        "left_context": left_context,
        "newspaper": candidate.get("newspaper", ""),
        "review_id": stable_review_id(audit_id, document_id, start, stop, label),
        "right_context": right_context,
        "source_index": source_index,
        "source_path": source_path,
        "suggested_label": label,
        "summary": summary,
        "surface": surface,
        "target_label": candidate.get("target_label") or label,
        "text": candidate.get("text", ""),
        "token_end_offsets": candidate.get("token_end_offsets", []),
        "token_start_offsets": candidate.get("token_start_offsets", []),
        "token_start": entity.get("token_start"),
        "token_stop": entity.get("token_stop"),
        "tokens": candidate.get("tokens", []),
        "start": start,
        "stop": stop,
    }


def candidate_context(text: str, start: int, stop: int, radius: int) -> tuple[str, str]:
    return text[max(0, start - radius) : start].strip(), text[stop : min(len(text), stop + radius)].strip()


def has_verified_audit_mark(candidate: dict[str, Any], entity: dict[str, Any]) -> bool:
    marks = candidate.get("audit_marks")
    if not isinstance(marks, list):
        return False
    label = str(entity.get("label") or "")
    start = int(entity["start"])
    stop = int(entity["stop"])
    for mark in marks:
        if not isinstance(mark, dict) or mark.get("status") != VERIFIED_STATUS:
            continue
        if int(mark.get("start", -1)) == start and int(mark.get("stop", -1)) == stop and str(mark.get("label") or "") == label:
            return True
    return False


def load_span_patches(path: Path, *, audit_id: str, target_label: str = "", context_radius: int = 80) -> list[dict[str, Any]]:
    patches: list[dict[str, Any]] = []
    for row_index, candidate in enumerate(load_jsonl(path), start=1):
        entities = candidate.get("predicted_entities") or candidate.get("candidate_spans") or []
        if not isinstance(entities, list):
            continue
        text = str(candidate.get("text") or "")
        for entity in entities:
            if not isinstance(entity, dict) or not entity.get("label"):
                continue
            if target_label and entity.get("label") != target_label and candidate.get("target_label") != target_label:
                continue
            if has_verified_audit_mark(candidate, entity):
                continue
            entity = dict(entity)
            if "left_context" not in entity or "right_context" not in entity:
                left, right = candidate_context(text, int(entity["start"]), int(entity["stop"]), context_radius)
                entity.setdefault("left_context", left)
                entity.setdefault("right_context", right)
            patches.append(
                span_patch(
                    audit_id=audit_id,
                    candidate=candidate,
                    entity=entity,
                    source_path=str(path),
                    source_index=row_index,
                )
            )
    patches.sort(key=lambda row: (str(row["document_id"]), int(row["start"]), int(row["stop"]), str(row["suggested_label"])))
    return patches


def summarize_queue(patches: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_label: dict[str, int] = {}
    by_language: dict[str, int] = {}
    pending = 0
    for patch in patches:
        decision = decisions.get(patch["review_id"])
        status = str(decision.get("audit_status") or decision.get("status")) if decision else "todo"
        if not is_verified(decision):
            pending += 1
        by_status[status] = by_status.get(status, 0) + 1
        label = str(patch["suggested_label"])
        language = str(patch.get("language") or "")
        by_label[label] = by_label.get(label, 0) + 1
        by_language[language] = by_language.get(language, 0) + 1
    return {
        "patches": len(patches),
        "pending": pending,
        "by_status": dict(sorted(by_status.items())),
        "by_label": dict(sorted(by_label.items())),
        "by_language": dict(sorted(by_language.items())),
    }


def clear_screen() -> None:
    review_ui.clear_screen()


def visible_context_bounds(patch: dict[str, Any], *, radius: int = CONTEXT_RADIUS) -> tuple[int, int]:
    text = str(patch.get("text") or "")
    start = int(patch["start"])
    stop = int(patch["stop"])
    return max(0, start - radius), min(len(text), stop + radius)


def format_highlighted_context(patch: dict[str, Any], *, color: bool = True, radius: int = CONTEXT_RADIUS) -> str:
    text = str(patch.get("text") or "")
    start = int(patch["start"])
    stop = int(patch["stop"])
    left, right = visible_context_bounds(patch, radius=radius)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(text) else ""
    surface = text[start:stop]
    if color and sys.stdout.isatty():
        surface = f"{SUGGESTION_STYLE}[P:{surface}]{RESET}"
    else:
        surface = f"[P:{surface}]"
    return f"{prefix}{text[left:start]}{surface}{text[stop:right]}{suffix}"


def numbered_tokens(patch: dict[str, Any]) -> str:
    if patch.get("tokens"):
        return review_ui.numbered_tokens(patch)
    rendered = []
    text = str(patch.get("text") or "")
    start = int(patch["start"])
    stop = int(patch["stop"])
    for index, match in enumerate(TOKEN_RE.finditer(text)):
        token = match.group(0)
        marker = "P" if match.start() < stop and match.end() > start else ""
        prefix = f"{index}@{match.start()}:{match.end()}:"
        rendered.append(f"[{marker}:{prefix}{token}]" if marker else f"{prefix}{token}")
    return " ".join(rendered)


def format_list(values: Any) -> str:
    if isinstance(values, list):
        return ", ".join(str(value) for value in values)
    return str(values or "")


def print_label_info(patch: dict[str, Any], label_metadata: dict[str, dict[str, Any]]) -> None:
    print("info")
    print(f"  metadata file: {', '.join(str(path) for path in DEFAULT_LABEL_METADATA)}")
    print(f"  source file: {patch.get('source_path', '')}")
    article_id = patch.get("document_id")
    if article_id:
        print(f"  impresso article: https://impresso-project.ch/app/article/{article_id}")
    print("  predicted spans:")
    token_start = patch.get("token_start")
    token_stop = patch.get("token_stop")
    token_span = f"{token_start}:{token_stop}" if token_start is not None else "<unknown>"
    print(f"    1: {token_span} {patch.get('surface', '')} [{patch.get('suggested_label', '')}]")
    labels = [str(patch.get("suggested_label") or ""), str(patch.get("target_label") or "")]
    for label in sorted({label for label in labels if label}):
        row = label_metadata.get(label)
        print(f"  label: {label}")
        if not row:
            print("    <no local metadata found>")
            continue
        print(f"    name: {row.get('display_name') or row.get('name') or ''}")
        active = row.get("active_period") or {}
        if isinstance(active, dict) and active:
            start = active.get("start") or "?"
            end = active.get("end") or "present/unknown"
            print(f"    active: {start} - {end}; {active.get('note', '')}")
        if row.get("description"):
            print(f"    description: {row['description']}")
        if row.get("annotation_note"):
            print(f"    annotation note: {row['annotation_note']}")
        review_ui.print_mention_profile(row)
        aliases_by_language = row.get("aliases_by_language") or {}
        for lang in ("de", "fr", "en"):
            if aliases_by_language.get(lang):
                print(f"    aliases {lang}: {format_list(aliases_by_language[lang])}")
        contextual_aliases = row.get("contextual_aliases") or []
        if contextual_aliases:
            print("    contextual aliases:")
            for alias in contextual_aliases:
                print(f"      - {alias.get('alias', '')}: {alias.get('note', '')}")
        sources = row.get("metadata_sources") or []
        if sources:
            print("    sources:")
            for source in sources:
                print(f"      - {source.get('type', 'source')}: {source.get('url', '')}")


def print_patch(patch: dict[str, Any], index: int, total: int, decision: dict[str, Any] | None) -> None:
    print("\n" + "=" * 88)
    print(f"{index}/{total} {patch['review_id']}")
    print(f"document: {patch['document_id']} [{patch.get('language', '')}] {patch.get('date', '')} {patch.get('newspaper', '')}")
    print(f"candidate label: {patch.get('target_label', '')}")
    print(f"reasons: audit suggested a missing span in an already annotated training document")
    if decision:
        print(f"existing decision: {decision.get('audit_marker', '')} {decision.get('choice')} {decision.get('correct_label', '')}")
    print("-" * 88)
    print(format_highlighted_context(patch))
    print("-" * 88)
    print("predicted spans:")
    token_start = patch.get("token_start")
    token_stop = patch.get("token_stop")
    token_span = f"{token_start}:{token_stop}" if token_start is not None else "<unknown>"
    print(f"  1: {token_span} {patch.get('surface', '')} [{patch['suggested_label']}]")
    print("choice meaning:")
    print("  a = accept/review suggested span; m = enter manual span")
    print("  r = reject suggested annotation for this item; s = skip temporarily")
    print("  i = show label/source info; N = show numbered tokens; q = quit")
    print("Choices: [a]ccept/review prediction span [m]anual span [r]eject annotation [s]kip [i]nfo [N]umbered tokens [q]uit")


def decision_record(
    patch: dict[str, Any],
    *,
    choice: str,
    reviewer: str,
    correct_label: str = "",
    start: Any = None,
    stop: Any = None,
    token_start: Any = None,
    token_stop: Any = None,
    notes: str = "",
) -> dict[str, Any]:
    reviewed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    marker_date = reviewed_at[:10]
    verified = choice in {"accept", "reject", "modify"}
    audit_status = VERIFIED_STATUS if verified else "skipped"
    span = {
        "label": correct_label or patch["suggested_label"],
        "start": int(start if start is not None else patch["start"]),
        "stop": int(stop if stop is not None else patch["stop"]),
    }
    if token_start is None:
        token_start = patch.get("token_start")
    if token_stop is None:
        token_stop = patch.get("token_stop")
    if token_start is not None and token_stop is not None:
        span["token_start"] = int(token_start)
        span["token_stop"] = int(token_stop)
    return {
        "audit_id": patch["audit_id"],
        "audit_marker": f"{reviewer}:{marker_date}:{audit_status}",
        "audit_status": audit_status,
        "choice": choice,
        "correct_label": correct_label or patch["suggested_label"],
        "document_id": patch["document_id"],
        "notes": notes,
        "review_id": patch["review_id"],
        "reviewed_at": reviewed_at,
        "reviewer": reviewer,
        "source": {
            "label": patch["suggested_label"],
            "start": patch["start"],
            "stop": patch["stop"],
            "surface": patch.get("surface", ""),
            "token_start": patch.get("token_start"),
            "token_stop": patch.get("token_stop"),
        },
        "span": span,
        "status": audit_status,
        "target_label": patch.get("target_label", ""),
    }


def split_surface_and_label(raw: str) -> tuple[str, str]:
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = raw.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        value = parts[0]
        if value.startswith("org.ent."):
            return "", value
        return value, ""
    return " ".join(parts[:-1]), parts[-1]


def token_offsets(patch: dict[str, Any]) -> tuple[list[int], list[int]]:
    starts = patch.get("token_start_offsets") if isinstance(patch.get("token_start_offsets"), list) else []
    ends = patch.get("token_end_offsets") if isinstance(patch.get("token_end_offsets"), list) else []
    if len(starts) != len(ends):
        return [], []
    return [int(value) for value in starts], [int(value) for value in ends]


def token_span_to_char_offsets(patch: dict[str, Any], token_start: int, token_stop: int) -> tuple[int, int]:
    starts, ends = token_offsets(patch)
    if not starts:
        raise ValueError("token offsets are not available for this candidate")
    if token_start < 0 or token_stop <= token_start or token_stop > len(starts):
        raise ValueError(f"token span must be within 0:{len(starts)} and use an exclusive stop")
    return starts[token_start], ends[token_stop - 1]


def nearest_visible_surface_span(patch: dict[str, Any], surface: str) -> tuple[int, int]:
    text = str(patch.get("text") or "")
    left, right = visible_context_bounds(patch)
    visible = text[left:right]
    matches = []
    search_from = 0
    while True:
        local_start = visible.find(surface, search_from)
        if local_start < 0:
            break
        start = left + local_start
        stop = start + len(surface)
        matches.append((abs(start - int(patch["start"])), start, stop))
        search_from = local_start + max(1, len(surface))
    if not matches:
        raise ValueError(f'surface "{surface}" not found in the visible context')
    _, start, stop = sorted(matches)[0]
    return start, stop


def resolve_manual_correction(patch: dict[str, Any], raw: str) -> tuple[int, int, str]:
    value = raw.strip()
    if not value:
        raise ValueError("empty correction")
    if value.startswith("org.ent."):
        return int(patch["start"]), int(patch["stop"]), review_ui.resolve_manual_label(value, patch, load_label_metadata(DEFAULT_LABEL_METADATA))
    if token_offsets(patch)[0] and patch.get("tokens"):
        span = review_ui.parse_manual_span(value, patch, load_label_metadata(DEFAULT_LABEL_METADATA))
        return int(span["start"]), int(span["stop"]), str(span["label"])
    match = SPAN_RE.match(value)
    if match:
        start = int(match.group("start"))
        stop = int(match.group("stop"))
        label = match.group("label")
        if token_offsets(patch)[0]:
            return (*token_span_to_char_offsets(patch, start, stop), label)
        return start, stop, label
    surface, label = split_surface_and_label(value)
    label = label or str(patch["suggested_label"])
    if not surface:
        return int(patch["start"]), int(patch["stop"]), label
    start, stop = nearest_visible_surface_span(patch, surface)
    return start, stop, label


def prompt_review(patches: list[dict[str, Any]], decisions_path: Path, reviewer: str, limit: int = 0) -> dict[str, Any]:
    decisions = latest_decisions(decisions_path)
    pending = [patch for patch in patches if not is_verified(decisions.get(patch["review_id"]))]
    if limit > 0:
        pending = pending[:limit]
    label_metadata = load_label_metadata(DEFAULT_LABEL_METADATA)
    reviewed = 0
    for index, patch in enumerate(pending, start=1):
        clear_screen()
        print_patch(patch, index, len(pending), decisions.get(patch["review_id"]))
        while True:
            raw_choice = input("> ").strip()
            if raw_choice == "N":
                print("numbered tokens/offsets:")
                print(numbered_tokens(patch))
                continue
            choice = raw_choice.lower()
            if choice in {"q", "quit"}:
                return {"reviewed": reviewed, "remaining": len(pending) - index + 1}
            if choice in {"i", "info"}:
                print_label_info(patch, label_metadata)
                continue
            if choice in {"a", "accept"}:
                record = decision_record(patch, choice="accept", reviewer=reviewer)
                break
            if choice in {"r", "reject"}:
                record = decision_record(patch, choice="reject", reviewer=reviewer)
                break
            if choice in {"s", "skip"}:
                record = decision_record(patch, choice="skip", reviewer=reviewer)
                break
            if choice in {"l", "label"}:
                correct_label = input("label> ").strip()
                if not correct_label:
                    print("label required")
                    continue
                record = decision_record(patch, choice="modify", reviewer=reviewer, correct_label=correct_label)
                break
            if choice in {"m", "modify", "b", "boundary"}:
                manual_spans = review_ui.prompt_manual_spans(patch, label_metadata)
                if manual_spans is None:
                    continue
                if len(manual_spans) != 1:
                    print("Audit span-patch decisions currently accept exactly one corrected span for this suggestion.")
                    continue
                span = manual_spans[0]
                record = decision_record(
                    patch,
                    choice="modify",
                    reviewer=reviewer,
                    correct_label=str(span["label"]),
                    start=int(span["start"]),
                    stop=int(span["stop"]),
                    token_start=int(span["token_start"]),
                    token_stop=int(span["token_stop"]),
                )
                break
            print("unknown choice")
        append_jsonl(decisions_path, record)
        decisions[patch["review_id"]] = record
        reviewed += 1
    return {"reviewed": reviewed, "remaining": max(0, len(pending) - reviewed)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review generic audit span patches.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--reviewer", default=os.environ.get("USER", ""))
    parser.add_argument("--target-label", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--summary-json", default="")
    parser.add_argument("--queue-jsonl", default="")
    parser.add_argument("--no-interactive", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    candidates = Path(args.candidates)
    decisions = Path(args.decisions)
    patches = load_span_patches(candidates, audit_id=args.audit_id, target_label=args.target_label)
    latest = latest_decisions(decisions)
    summary = summarize_queue(patches, latest)
    pending_patches = [patch for patch in patches if not is_verified(latest.get(patch["review_id"]))]
    if args.queue_jsonl:
        write_jsonl(Path(args.queue_jsonl), pending_patches)
    if args.summary_json:
        write_json(Path(args.summary_json), summary)
    if not args.no_interactive:
        summary.update(prompt_review(patches, decisions, args.reviewer, args.limit))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
