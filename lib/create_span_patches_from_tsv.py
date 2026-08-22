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
    old_labels: tuple[str, ...] = ()
    new_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class Match:
    row: dict[str, Any]
    token_start: int
    token_stop: int


@dataclass(frozen=True)
class SplitSpec:
    name: str
    input_jsonl: Path
    candidates: Path
    decisions: Path
    audit_id: str
    summary_json: Path | None = None


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


def parse_split_spec(raw: str) -> tuple[str, Path]:
    name, separator, path = raw.partition("=")
    if not separator or not name.strip() or not path.strip():
        raise ValueError(f"split path must use NAME=PATH syntax: {raw!r}")
    return name.strip(), Path(path.strip())


def split_mapping(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        name, path = parse_split_spec(value)
        result[name] = path
    return result


def split_specs(args: argparse.Namespace) -> list[SplitSpec]:
    inputs = split_mapping(args.split_input_jsonl)
    candidates = split_mapping(args.split_candidates)
    decisions = split_mapping(args.split_decisions)
    summaries = split_mapping(args.split_summary_json)
    audit_ids = dict(parse_split_spec(value) for value in args.split_audit_id)
    missing: list[str] = []
    for name in inputs:
        if name not in candidates:
            missing.append(f"--split-candidates {name}=...")
        if name not in decisions:
            missing.append(f"--split-decisions {name}=...")
        if name not in audit_ids:
            missing.append(f"--split-audit-id {name}=...")
    if missing:
        raise ValueError("missing split options: " + ", ".join(missing))
    return [
        SplitSpec(
            name=name,
            input_jsonl=inputs[name],
            candidates=candidates[name],
            decisions=decisions[name],
            audit_id=str(audit_ids[name]),
            summary_json=summaries.get(name),
        )
        for name in inputs
    ]


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def looks_like_bio_label(value: str) -> bool:
    return normalize_bio_label(value) == "O" or value.startswith("B-") or value.startswith("I-")


def normalize_bio_label(value: str) -> str:
    stripped = value.strip()
    if stripped in {"-", "o", "O"}:
        return "O"
    return stripped


def parse_tsv_paste(raw: str) -> TokenSequence:
    tokens: list[str] = []
    old_labels: list[str] = []
    new_labels: list[str] = []
    rows: list[tuple[str, str | None, str | None]] = []
    metadata: dict[str, str] = {}
    for raw_line in raw.splitlines():
        line = strip_ansi(raw_line.strip("\n"))
        if not line.strip():
            continue
        if line.strip() == "-" or line.strip().startswith("```"):
            continue
        if line.startswith("#"):
            key, separator, value = line[1:].strip().partition("=")
            if separator:
                metadata[key.strip()] = value.strip()
            continue
        columns = line.split()
        if columns[:2] == ["TOKEN", "NERTAG"] or columns[:1] == ["TOKEN"]:
            continue
        if len(columns) <= 2 and looks_like_bio_label(columns[0].strip()):
            continue
        token = columns[0].strip()
        if token:
            old = normalize_bio_label(columns[1]) if len(columns) >= 2 else None
            new = normalize_bio_label(columns[2]) if len(columns) >= 3 else None
            rows.append(
                (
                    token,
                    old,
                    new,
                )
            )
    has_new_column = any(new is not None for _token, _old, new in rows)
    for token, old, new in rows:
        tokens.append(token)
        if old is not None:
            old_labels.append(old)
        if has_new_column:
            if old is None:
                raise ValueError("three-column TOKEN OLD NEW patches require an OLD label on every token line")
            new_labels.append(new if new is not None else old)
    if not tokens:
        raise ValueError("no tokens found in pasted TSV")
    return TokenSequence(tokens=tuple(tokens), metadata=metadata, old_labels=tuple(old_labels), new_labels=tuple(new_labels))


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


def labels_match(actual: list[str], expected: Iterable[str]) -> bool:
    return actual == [str(label) for label in expected]


def label_from_bio(tag: str) -> str:
    if tag == "O":
        return "O"
    prefix, separator, label = tag.partition("-")
    if separator and prefix in {"B", "I"} and label:
        return label
    raise ValueError(f"invalid BIO label in NEW column: {tag!r}")


def target_from_new_labels(sequence: TokenSequence, label_metadata: dict[str, dict[str, Any]] | None = None) -> tuple[str, int, int] | None:
    targets = targets_from_new_labels(sequence, label_metadata)
    if not targets:
        return None
    if len(targets) > 1:
        raise ValueError("NEW column defines multiple entity spans; use targets_from_new_labels")
    return targets[0]


def targets_from_new_labels(sequence: TokenSequence, label_metadata: dict[str, dict[str, Any]] | None = None) -> list[tuple[str, int, int]]:
    if not sequence.new_labels:
        return []
    non_o = [index for index, tag in enumerate(sequence.new_labels) if tag != "O"]
    if not non_o:
        old_non_o = [index for index, tag in enumerate(sequence.old_labels) if tag != "O"]
        if old_non_o:
            if old_non_o != list(range(old_non_o[0], old_non_o[-1] + 1)):
                raise ValueError("OLD column must contain one contiguous annotated span when NEW is all O")
            return [("O", old_non_o[0], old_non_o[-1] + 1)]
        return [("O", 0, len(sequence.tokens))]
    targets: list[tuple[str, int, int]] = []
    index = 0
    while index < len(sequence.new_labels):
        tag = sequence.new_labels[index]
        if tag == "O":
            index += 1
            continue
        if not tag.startswith("B-"):
            raise ValueError(f"NEW column entity span must start with B- label at token {index}: {tag!r}")
        label = label_from_bio(tag)
        start = index
        index += 1
        while index < len(sequence.new_labels) and sequence.new_labels[index] != "O":
            continuation = sequence.new_labels[index]
            if continuation.startswith("B-"):
                break
            if not continuation.startswith("I-"):
                raise ValueError(f"invalid BIO label in NEW column: {continuation!r}")
            continuation_label = label_from_bio(continuation)
            if continuation_label != label:
                raise ValueError(
                    f"NEW column I- label does not match current entity at token {index}: expected I-{label}, got {continuation!r}"
                )
            index += 1
        targets.append((resolve_label(label, label_metadata), start, index))
    return targets


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


def actionable_matches_for_target(
    matches: Iterable[Match],
    *,
    label: str,
    relative_start: int,
    relative_stop: int,
    include_existing: bool = False,
    old_labels: tuple[str, ...] = (),
    new_labels: tuple[str, ...] = (),
) -> list[Match]:
    if include_existing:
        return list(matches)
    actionable = []
    for match in matches:
        if old_labels and new_labels and old_labels != new_labels and current_labels(match) == list(old_labels):
            actionable.append(match)
            continue
        submatch = Match(row=match.row, token_start=match.token_start + relative_start, token_stop=match.token_start + relative_stop)
        labels = current_labels(submatch)
        if label == "O":
            if any(current != "O" for current in labels):
                actionable.append(match)
            continue
        if labels != expected_labels(label, submatch.token_stop - submatch.token_start):
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
    target_span: tuple[int, int] | None = None,
) -> dict[str, Any]:
    rows = load_jsonl(input_jsonl)
    sequence = parse_tsv_paste(pasted_tsv)
    inferred_targets = targets_from_new_labels(sequence, label_metadata)
    if inferred_targets:
        targets = inferred_targets
        label = targets[0][0]
    else:
        label = resolve_label(label, label_metadata)
        relative_start, relative_stop = target_span or (0, len(sequence.tokens))
        targets = [(label, relative_start, relative_stop)]
    raw_matches = find_token_matches(rows, sequence)
    if sequence.old_labels:
        raw_matches = [match for match in raw_matches if labels_match(current_labels(match), sequence.old_labels)]
    if selected_matches is not None:
        matches = selected_matches
    else:
        matches_by_key: dict[tuple[str, int, int], Match] = {}
        for target_label, relative_start, relative_stop in targets:
            target_matches = actionable_matches_for_target(
                raw_matches,
                label=target_label,
                relative_start=relative_start,
                relative_stop=relative_stop,
                include_existing=include_existing,
                old_labels=sequence.old_labels,
                new_labels=sequence.new_labels,
            )
            for match in target_matches:
                matches_by_key[(row_id(match.row), match.token_start, match.token_stop)] = match
        matches = [matches_by_key[key] for key in sorted(matches_by_key)]
    if not matches:
        raise ValueError(f"no matches found for token sequence: {' '.join(sequence.tokens)}")

    target_matches = [
        (
            target_label,
            Match(row=match.row, token_start=match.token_start + relative_start, token_stop=match.token_start + relative_stop),
        )
        for match in matches
        for target_label, relative_start, relative_stop in targets
    ]
    new_candidates = [candidate_for_match(match, audit_id=audit_id, label=target_label) for target_label, match in target_matches]
    new_keys = {candidate_key(candidate) for candidate in new_candidates}
    existing_candidates = load_jsonl(candidates_path) if candidates_path.is_file() else []
    all_candidates = merge_candidates(existing_candidates, new_candidates)
    write_jsonl(candidates_path, all_candidates)

    target_labels = {target_label for target_label, _start, _stop in targets}
    patches = [
        patch
        for patch in load_span_patches(candidates_path, audit_id=audit_id)
        if str(patch.get("suggested_label") or "") in target_labels
    ]
    patch_ids = {patch["review_id"] for patch in patches}
    existing_decisions = load_jsonl(decisions_path) if decisions_path.is_file() else []
    existing_decision_ids = {str(row.get("review_id") or "") for row in existing_decisions}
    current_patch_ids = {
        patch["review_id"]
        for patch in patches
        if (patch["audit_id"], patch["document_id"], int(patch["start"]), int(patch["stop"]), patch["suggested_label"]) in new_keys
    }
    existing_current_decisions = sorted(current_patch_ids & existing_decision_ids)
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
        "label": label if len(target_labels) == 1 else "",
        "labels": sorted(target_labels),
        "matches": len(matches),
        "mentions": len(target_matches),
        "new_candidates": len(new_candidates),
        "new_decisions": len(new_decisions),
        "existing_decisions": len(existing_current_decisions),
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
    print("Paste TSV token lines. Use TOKEN NERTAG or TOKEN OLD NEW columns. Finish with an empty line.")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
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


def infer_or_prompt_label(
    *,
    sequence: TokenSequence,
    label_metadata: dict[str, dict[str, Any]],
    raw_label: str,
    target_only: bool = False,
    non_o_target_only: bool = False,
) -> tuple[str, tuple[int, int] | None] | int:
    try:
        inferred_targets = targets_from_new_labels(sequence, label_metadata)
    except ValueError as exc:
        print(exc)
        return 1
    if non_o_target_only:
        return 0 if inferred_targets and any(target[0] != "O" for target in inferred_targets) else 1
    if target_only:
        return 0 if inferred_targets else 1
    if inferred_targets:
        labels = sorted({target[0] for target in inferred_targets})
        spans = ", ".join(f"{label} tokens={start}:{stop}" for label, start, stop in inferred_targets)
        label = labels[0]
        relative_start, relative_stop = inferred_targets[0][1], inferred_targets[0][2]
        print(f"targets from NEW column: {len(inferred_targets)} mention(s): {spans}")
        return label, (relative_start, relative_stop)
    try:
        raw_label = raw_label or input("Entity label: ").strip()
    except EOFError:
        print("entity label is required for two-column TSV patches; pass --label or use TOKEN OLD NEW columns")
        return 1
    if not raw_label:
        print("entity label is required")
        return 1
    try:
        return resolve_label(raw_label, label_metadata), None
    except ValueError as exc:
        print(exc)
        return 1


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
    parser.add_argument("--allow-no-matches", action="store_true")
    parser.add_argument("--detect-target-only", action="store_true", help="Read pasted TSV and exit 0 if TOKEN OLD NEW defines a target.")
    parser.add_argument("--detect-non-o-target-only", action="store_true", help="Read pasted TSV and exit 0 if TOKEN OLD NEW defines a non-O target.")
    parser.add_argument("--split-input-jsonl", action="append", default=[], metavar="SPLIT=PATH")
    parser.add_argument("--split-candidates", action="append", default=[], metavar="SPLIT=PATH")
    parser.add_argument("--split-decisions", action="append", default=[], metavar="SPLIT=PATH")
    parser.add_argument("--split-audit-id", action="append", default=[], metavar="SPLIT=ID")
    parser.add_argument("--split-summary-json", action="append", default=[], metavar="SPLIT=PATH")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pasted_tsv = read_pasted_block()
    sequence = parse_tsv_paste(pasted_tsv)
    label_metadata = review_ui.load_label_metadata(args.label_metadata or DEFAULT_LABEL_METADATA)
    inferred = infer_or_prompt_label(
        sequence=sequence,
        label_metadata=label_metadata,
        raw_label=args.label,
        target_only=args.detect_target_only,
        non_o_target_only=args.detect_non_o_target_only,
    )
    if isinstance(inferred, int):
        return inferred
    label, target_span = inferred
    raw_label = label
    try:
        label = resolve_label(raw_label, label_metadata)
    except ValueError as exc:
        print(exc)
        return 1
    if label != raw_label:
        print(f"resolved entity label: {label}")
    if args.split_input_jsonl:
        try:
            specs = split_specs(args)
        except ValueError as exc:
            print(exc)
            return 1
        summaries = {}
        for spec in specs:
            print(f"=== {spec.name} ===")
            try:
                summary = build_accepted_patches(
                    input_jsonl=spec.input_jsonl,
                    candidates_path=spec.candidates,
                    decisions_path=spec.decisions,
                    audit_id=spec.audit_id,
                    label=label,
                    pasted_tsv=pasted_tsv,
                    reviewer=args.reviewer,
                    label_metadata=label_metadata,
                    include_existing=args.include_existing,
                    target_span=target_span,
                )
            except ValueError as exc:
                if args.allow_no_matches and str(exc).startswith("no matches found"):
                    print(exc)
                    target_labels = sorted({target[0] for target in targets_from_new_labels(sequence, label_metadata)} or {label})
                    summary = {
                        "audit_id": spec.audit_id,
                        "candidates": str(spec.candidates),
                        "decisions": str(spec.decisions),
                        "label": label,
                        "labels": target_labels,
                        "matches": 0,
                        "mentions": 0,
                        "new_candidates": 0,
                        "new_decisions": 0,
                        "existing_decisions": 0,
                        "tokens": list(sequence.tokens),
                    }
                else:
                    print(exc)
                    return 1
            if spec.summary_json:
                write_json(spec.summary_json, summary)
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            print(
                f"mentions queued in {spec.name}: {summary['new_decisions']} new, "
                f"{summary.get('existing_decisions', 0)} already queued, "
                f"{summary['mentions']} matching mention candidate(s)"
            )
            summaries[spec.name] = summary
        if args.summary_json:
            write_json(args.summary_json, summaries)
        return 0
    rows = load_jsonl(args.input_jsonl)
    raw_matches = find_token_matches(rows, sequence)
    if sequence.old_labels:
        raw_matches = [match for match in raw_matches if labels_match(current_labels(match), sequence.old_labels)]
    if not raw_matches:
        print(f"no matches found for token sequence: {' '.join(sequence.tokens)}")
        return 0 if args.allow_no_matches else 1
    relative_start, relative_stop = target_span or (0, len(sequence.tokens))
    matches = actionable_matches_for_target(
        raw_matches,
        label=label,
        relative_start=relative_start,
        relative_stop=relative_stop,
        include_existing=args.include_existing,
        old_labels=sequence.old_labels,
        new_labels=sequence.new_labels,
    )
    skipped = len(raw_matches) - len(matches)
    if skipped:
        print(f"skipped {skipped} already-correct/non-actionable match(es); pass --include-existing to show them")
    if not matches:
        print(f"no actionable matches found for label {label}")
        return 0 if args.allow_no_matches else 1
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
        target_span=target_span,
    )
    if args.summary_json:
        write_json(args.summary_json, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    print(
        f"mentions queued: {summary['new_decisions']} new, "
        f"{summary.get('existing_decisions', 0)} already queued, "
        f"{summary['mentions']} matching mention candidate(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
