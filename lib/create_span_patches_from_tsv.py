from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from lib import review_ui
from lib.span_patch_review import decision_record, load_span_patches, write_jsonl


DEFAULT_LABEL_METADATA = [Path("resources/newsagency_seeds.json"), Path("resources/radiostation_seeds.json")]
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class TokenSequence:
    tokens: tuple[str, ...]
    metadata: dict[str, str]


@dataclass(frozen=True)
class Match:
    row: dict[str, Any]
    token_start: int
    token_stop: int


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            rows.append(row)
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def parse_tsv_paste(raw: str) -> TokenSequence:
    tokens: list[str] = []
    metadata: dict[str, str] = {}
    for raw_line in raw.splitlines():
        line = strip_ansi(raw_line.strip("\n"))
        if not line.strip():
            continue
        if line.startswith("#"):
            key, separator, value = line[1:].strip().partition("=")
            if separator:
                metadata[key.strip()] = value.strip()
            continue
        columns = line.split("\t") if "\t" in line else line.split()
        if columns[:2] == ["TOKEN", "NERTAG"] or columns[:1] == ["TOKEN"]:
            continue
        token = columns[0].strip()
        if token:
            tokens.append(token)
    if not tokens:
        raise ValueError("no tokens found in pasted TSV")
    return TokenSequence(tokens=tuple(tokens), metadata=metadata)


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("document_id") or row.get("id") or "")


def row_matches_document(row: dict[str, Any], document_id: str) -> bool:
    return document_id in {str(row.get("document_id") or ""), str(row.get("id") or "")}


def find_token_matches(rows: Iterable[dict[str, Any]], sequence: TokenSequence) -> list[Match]:
    wanted = list(sequence.tokens)
    document_id = sequence.metadata.get("document_id") or sequence.metadata.get("doc_id") or ""
    matches: list[Match] = []
    for row in rows:
        if document_id and not row_matches_document(row, document_id):
            continue
        tokens = [str(token) for token in row.get("tokens") or []]
        for start in range(0, len(tokens) - len(wanted) + 1):
            stop = start + len(wanted)
            if tokens[start:stop] == wanted:
                matches.append(Match(row=row, token_start=start, token_stop=stop))
    return sorted(matches, key=lambda item: (row_id(item.row), item.token_start, item.token_stop))


def current_labels(match: Match) -> list[str]:
    return [str(label) for label in (match.row.get("token_labels") or [])[match.token_start : match.token_stop]]


def expected_labels(label: str, length: int) -> list[str]:
    if label == "O":
        return ["O"] * length
    return [f"{'B' if index == 0 else 'I'}-{label}" for index in range(length)]


def match_context(match: Match, *, radius: int = 3) -> str:
    tokens = [str(token) for token in match.row.get("tokens") or []]
    left = tokens[max(0, match.token_start - radius) : match.token_start]
    focus = tokens[match.token_start : match.token_stop]
    right = tokens[match.token_stop : match.token_stop + radius]
    prefix = "... " if match.token_start > radius else ""
    suffix = " ..." if match.token_stop + radius < len(tokens) else ""
    return f"{prefix}{' '.join(left)} [{' '.join(focus)}] {' '.join(right)}{suffix}".strip()


def actionable_matches(matches: Iterable[Match], *, label: str, include_existing: bool = False) -> list[Match]:
    if include_existing:
        return list(matches)
    actionable = []
    for match in matches:
        labels = current_labels(match)
        if label == "O":
            if any(current != "O" for current in labels):
                actionable.append(match)
            continue
        if labels != expected_labels(label, match.token_stop - match.token_start):
            actionable.append(match)
    return actionable


def char_offsets(row: dict[str, Any], token_start: int, token_stop: int) -> tuple[int, int]:
    starts = row.get("token_start_offsets") or []
    stops = row.get("token_end_offsets") or []
    if token_start < 0 or token_stop <= token_start or token_stop > len(starts) or token_stop > len(stops):
        raise ValueError(f"{row_id(row)}: token span {token_start}:{token_stop} is out of range")
    return int(starts[token_start]), int(stops[token_stop - 1])


def candidate_for_match(match: Match, *, audit_id: str, label: str) -> dict[str, Any]:
    row = match.row
    start, stop = char_offsets(row, match.token_start, match.token_stop)
    text = str(row.get("text") or "")
    surface = text[start:stop]
    return {
        "audit_id": audit_id,
        "audit_mode": "manual-tsv-remove" if label == "O" else "manual-tsv-patch",
        "date": row.get("date", ""),
        "document_id": row_id(row),
        "id": row.get("id", row_id(row)),
        "language": row.get("language", ""),
        "newspaper": row.get("newspaper", ""),
        "target_label": label,
        "text": text,
        "tokens": row.get("tokens", []),
        "token_start_offsets": row.get("token_start_offsets", []),
        "token_end_offsets": row.get("token_end_offsets", []),
        "predicted_entities": [
            {
                "label": label,
                "start": start,
                "stop": stop,
                "surface": surface,
                "token_start": match.token_start,
                "token_stop": match.token_stop,
            }
        ],
    }


def candidate_key(candidate: dict[str, Any]) -> tuple[str, str, int, int, str]:
    entity = (candidate.get("predicted_entities") or [{}])[0]
    return (
        str(candidate.get("audit_id") or ""),
        str(candidate.get("document_id") or ""),
        int(entity.get("start")),
        int(entity.get("stop")),
        str(entity.get("label") or ""),
    )


def merge_candidates(existing: list[dict[str, Any]], new_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {candidate_key(candidate): candidate for candidate in existing}
    for candidate in new_candidates:
        by_key.setdefault(candidate_key(candidate), candidate)
    return [by_key[key] for key in sorted(by_key)]


def build_accepted_patches(
    *,
    input_jsonl: Path,
    candidates_path: Path,
    decisions_path: Path,
    audit_id: str,
    label: str,
    pasted_tsv: str,
    reviewer: str,
    label_metadata: dict[str, dict[str, Any]] | None = None,
    selected_matches: list[Match] | None = None,
    include_existing: bool = False,
) -> dict[str, Any]:
    label = resolve_label(label, label_metadata)
    rows = load_jsonl(input_jsonl)
    sequence = parse_tsv_paste(pasted_tsv)
    matches = selected_matches if selected_matches is not None else actionable_matches(find_token_matches(rows, sequence), label=label, include_existing=include_existing)
    if not matches:
        raise ValueError(f"no matches found for token sequence: {' '.join(sequence.tokens)}")

    new_candidates = [candidate_for_match(match, audit_id=audit_id, label=label) for match in matches]
    new_keys = {candidate_key(candidate) for candidate in new_candidates}
    existing_candidates = load_jsonl(candidates_path) if candidates_path.is_file() else []
    all_candidates = merge_candidates(existing_candidates, new_candidates)
    write_jsonl(candidates_path, all_candidates)

    patches = load_span_patches(candidates_path, audit_id=audit_id, target_label=label)
    patch_ids = {patch["review_id"] for patch in patches}
    existing_decisions = load_jsonl(decisions_path) if decisions_path.is_file() else []
    existing_decision_ids = {str(row.get("review_id") or "") for row in existing_decisions}
    new_decisions = [
        decision_record(patch, choice="accept", reviewer=reviewer)
        for patch in patches
        if patch["review_id"] in patch_ids
        and patch["review_id"] not in existing_decision_ids
        and (patch["audit_id"], patch["document_id"], int(patch["start"]), int(patch["stop"]), patch["suggested_label"]) in new_keys
    ]
    write_jsonl(decisions_path, [*existing_decisions, *new_decisions])
    return {
        "audit_id": audit_id,
        "candidates": str(candidates_path),
        "decisions": str(decisions_path),
        "label": label,
        "matches": len(matches),
        "new_candidates": len(new_candidates),
        "new_decisions": len(new_decisions),
        "tokens": list(sequence.tokens),
    }


def resolve_label(raw_label: str, label_metadata: dict[str, dict[str, Any]] | None = None) -> str:
    if raw_label.strip() == "O":
        return "O"
    label_metadata = label_metadata or review_ui.load_label_metadata(DEFAULT_LABEL_METADATA)
    label = review_ui.resolve_manual_label(raw_label, {}, label_metadata)
    if label not in label_metadata:
        raise ValueError(f"unknown entity label {raw_label!r}; use a known canonical id or full label")
    return label


def read_pasted_block() -> str:
    print("Paste TSV token lines. Finish with a single '.' line.")
    lines = []
    while True:
        line = input()
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines)


def print_matches(matches: list[Match], label: str) -> None:
    print(f"Found {len(matches)} match(es) for label {label}:")
    for index, match in enumerate(matches, start=1):
        row = match.row
        start, stop = char_offsets(row, match.token_start, match.token_stop)
        surface = str(row.get("text") or "")[start:stop]
        labels = " ".join(current_labels(match))
        print(f"  {index}. {row_id(row)} tokens={match.token_start}:{match.token_stop} surface={surface!r} current={labels}")
        print(f"     context: {match_context(match)}")


def parse_match_selection(raw: str, total: int) -> list[int]:
    value = raw.strip().lower()
    if value in {"all", "a", "y", "yes"}:
        return list(range(total))
    if value in {"", "n", "no", "none", "q", "quit"}:
        return []
    selected: set[int] = set()
    for part in value.replace(",", " ").split():
        if "-" in part:
            left, right = part.split("-", 1)
            if not left.isdigit() or not right.isdigit():
                raise ValueError(f"invalid selection {part!r}")
            start = int(left)
            stop = int(right)
            if start > stop:
                start, stop = stop, start
            selected.update(range(start - 1, stop))
        else:
            if not part.isdigit():
                raise ValueError(f"invalid selection {part!r}")
            selected.add(int(part) - 1)
    invalid = [index + 1 for index in sorted(selected) if index < 0 or index >= total]
    if invalid:
        raise ValueError(f"selection out of range: {', '.join(str(index) for index in invalid)}")
    return sorted(selected)


def select_matches(matches: list[Match], label: str) -> list[Match]:
    print_matches(matches, label)
    while True:
        raw = input("Select matches to patch (e.g. 1,3-5 or all; empty abort): ")
        try:
            indexes = parse_match_selection(raw, len(matches))
        except ValueError as exc:
            print(exc)
            continue
        return [matches[index] for index in indexes]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create accepted span-patch decisions from pasted TOKEN/NERTAG TSV lines.")
    parser.add_argument("--input-jsonl", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--label-metadata", action="append", type=Path, default=[])
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--include-existing", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pasted_tsv = read_pasted_block()
    sequence = parse_tsv_paste(pasted_tsv)
    raw_label = args.label or input("Entity label: ").strip()
    if not raw_label:
        print("entity label is required")
        return 1
    label_metadata = review_ui.load_label_metadata(args.label_metadata or DEFAULT_LABEL_METADATA)
    try:
        label = resolve_label(raw_label, label_metadata)
    except ValueError as exc:
        print(exc)
        return 1
    if label != raw_label:
        print(f"resolved entity label: {label}")
    rows = load_jsonl(args.input_jsonl)
    raw_matches = find_token_matches(rows, sequence)
    if not raw_matches:
        print(f"no matches found for token sequence: {' '.join(sequence.tokens)}")
        return 1
    matches = actionable_matches(raw_matches, label=label, include_existing=args.include_existing)
    skipped = len(raw_matches) - len(matches)
    if skipped:
        print(f"skipped {skipped} already-correct/non-actionable match(es); pass --include-existing to show them")
    if not matches:
        print(f"no actionable matches found for label {label}")
        return 1
    selected_matches = matches if args.yes else select_matches(matches, label)
    if not selected_matches:
        print("aborted")
        return 1
    summary = build_accepted_patches(
        input_jsonl=args.input_jsonl,
        candidates_path=args.candidates,
        decisions_path=args.decisions,
        audit_id=args.audit_id,
        label=label,
        pasted_tsv=pasted_tsv,
        reviewer=args.reviewer,
        label_metadata=label_metadata,
        selected_matches=selected_matches,
        include_existing=args.include_existing,
    )
    if args.summary_json:
        write_json(args.summary_json, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
