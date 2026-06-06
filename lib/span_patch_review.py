from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


CLEAR_SCREEN = "\033[2J\033[H"
VERIFIED_STATUS = "verified"


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
        "token_start": entity.get("token_start"),
        "token_stop": entity.get("token_stop"),
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
        if status == "todo":
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
    if sys.stdout.isatty() and os.environ.get("TERM") not in {"", "dumb"}:
        print(CLEAR_SCREEN, end="")


def print_patch(patch: dict[str, Any], index: int, total: int, decision: dict[str, Any] | None) -> None:
    print("\n" + "=" * 88)
    print(f"{index}/{total} {patch['review_id']}")
    print(f"document: {patch['document_id']} [{patch.get('language', '')}] {patch.get('date', '')} {patch.get('newspaper', '')}")
    print(f"summary: {patch.get('summary', '')}")
    print(f"target: {patch.get('target_label', '')}")
    print(f"suggestion: {patch['start']}:{patch['stop']} \"{patch.get('surface', '')}\" [{patch['suggested_label']}]")
    if patch.get("token_start") is not None:
        print(f"tokens: {patch.get('token_start')}:{patch.get('token_stop')}")
    if decision:
        print(f"existing decision: {decision.get('audit_marker', '')} {decision.get('choice')} {decision.get('correct_label', '')}")
    print("-" * 88)
    print(f"... {patch.get('left_context', '')} >>>{patch.get('surface', '')}<<< {patch.get('right_context', '')} ...")
    print("-" * 88)
    print("Choices: [a]ccept [r]eject [m]odify label/span [s]kip [q]uit")


def decision_record(patch: dict[str, Any], *, choice: str, reviewer: str, correct_label: str = "", start: Any = None, stop: Any = None, notes: str = "") -> dict[str, Any]:
    reviewed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    marker_date = reviewed_at[:10]
    verified = choice in {"accept", "reject", "modify"}
    audit_status = VERIFIED_STATUS if verified else "skipped"
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
        "span": {
            "label": correct_label or patch["suggested_label"],
            "start": int(start if start is not None else patch["start"]),
            "stop": int(stop if stop is not None else patch["stop"]),
        },
        "status": audit_status,
        "target_label": patch.get("target_label", ""),
    }


def prompt_review(patches: list[dict[str, Any]], decisions_path: Path, reviewer: str, limit: int = 0) -> dict[str, Any]:
    decisions = latest_decisions(decisions_path)
    pending = [patch for patch in patches if not is_verified(decisions.get(patch["review_id"]))]
    if limit > 0:
        pending = pending[:limit]
    reviewed = 0
    for index, patch in enumerate(pending, start=1):
        clear_screen()
        print_patch(patch, index, len(pending), decisions.get(patch["review_id"]))
        while True:
            choice = input("> ").strip().lower()
            if choice in {"q", "quit"}:
                return {"reviewed": reviewed, "remaining": len(pending) - index + 1}
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
                raw = input("start:stop label> ").strip()
                parts = raw.split()
                if len(parts) != 2 or ":" not in parts[0]:
                    print("expected: 123:128 org.ent.pressagency.havas")
                    continue
                raw_start, raw_stop = parts[0].split(":", 1)
                record = decision_record(
                    patch,
                    choice="modify",
                    reviewer=reviewer,
                    correct_label=parts[1],
                    start=int(raw_start),
                    stop=int(raw_stop),
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
