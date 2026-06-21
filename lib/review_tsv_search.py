from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lib import review_ui
from lib.create_span_patches_from_tsv import Match, build_accepted_patches, load_jsonl, row_id, strip_ansi
from lib.tsv_hit_pager import build_block, document_bounds, find_hits, hit_label_for_hit, hit_title, load_lines, parse_token_line


@dataclass(frozen=True)
class TsvHit:
    hit: tuple[int, int]
    document_id: str
    token_start: int
    token_stop: int


def metadata_for_document(lines: list[str], hit: tuple[int, int]) -> dict[str, str]:
    start, _end = document_bounds(lines, hit)
    metadata: dict[str, str] = {}
    for line in lines[start : hit[0] + 1]:
        line = line.strip()
        if not line.startswith("#"):
            continue
        key, separator, value = line[1:].strip().partition("=")
        if separator:
            metadata[key.strip()] = value.strip()
    return metadata


def token_index_for_line(lines: list[str], hit: tuple[int, int], line_index: int) -> int:
    document_start, _document_end = document_bounds(lines, hit)
    token_index = 0
    for index in range(document_start, line_index + 1):
        if parse_token_line(lines[index]) is None:
            continue
        if index == line_index:
            return token_index
        token_index += 1
    raise ValueError(f"line {line_index} is not a token line")


def tsv_hit(lines: list[str], hit: tuple[int, int]) -> TsvHit:
    metadata = metadata_for_document(lines, hit)
    document_id = metadata.get("document_id") or metadata.get("doc_id") or ""
    if not document_id:
        raise ValueError(f"hit at line {hit[0] + 1} has no document_id/doc_id metadata")
    return TsvHit(
        hit=hit,
        document_id=document_id,
        token_start=token_index_for_line(lines, hit, hit[0]),
        token_stop=token_index_for_line(lines, hit, hit[1] - 1) + 1,
    )


def tokens_from_tsv_lines(raw_lines: list[str]) -> list[str]:
    tokens: list[str] = []
    for line in raw_lines:
        line = strip_ansi(line)
        parsed = parse_token_line(line if line.endswith("\n") else f"{line}\n")
        if parsed is not None:
            token, _label = parsed
            tokens.append(token)
    if not tokens:
        raise ValueError("no TSV token lines found")
    return tokens


def visible_token_bounds(lines: list[str], hit: tuple[int, int], *, context: int) -> tuple[int, int]:
    start, end = hit
    document_start, document_end = document_bounds(lines, hit)
    block_start = max(document_start, start - context)
    block_end = min(document_end, end + context)
    visible_indexes = [
        token_index_for_line(lines, hit, index)
        for index in range(block_start, block_end)
        if parse_token_line(lines[index]) is not None
    ]
    if not visible_indexes:
        current = tsv_hit(lines, hit)
        return current.token_start, current.token_stop
    return min(visible_indexes), max(visible_indexes) + 1


def nearest_token_sequence(row: dict[str, Any], wanted: list[str], default: tuple[int, int], *, bounds: tuple[int, int] | None = None) -> tuple[int, int]:
    tokens = [str(token) for token in row.get("tokens") or []]
    matches: list[tuple[int, int]] = []
    length = len(wanted)
    search_start = 0
    search_stop = len(tokens)
    if bounds is not None:
        search_start, search_stop = bounds
    for start in range(0, len(tokens) - length + 1):
        stop = start + length
        if start < search_start or stop > search_stop:
            continue
        if tokens[start:stop] == wanted:
            matches.append((start, stop))
    if not matches:
        scope = "visible context" if bounds is not None else "this document"
        raise ValueError(f"{row_id(row)}: pasted TSV token sequence not found in {scope}: {' '.join(wanted)}")
    default_start, _default_stop = default
    return min(matches, key=lambda item: (abs(item[0] - default_start), item[0], item[1]))


def read_annotation_span(row: dict[str, Any], default: tuple[int, int], *, bounds: tuple[int, int]) -> tuple[int, int]:
    first = input("paste TSV token line(s) [Enter = highlighted hit; finish multi-line paste with empty line]: ")
    if not first.strip():
        return default
    raw_lines = [first]
    while True:
        line = input("more TSV lines [Enter = done]: ")
        if not line.strip() or line.strip() == ".":
            break
        raw_lines.append(line)
    wanted = tokens_from_tsv_lines(raw_lines)
    return nearest_token_sequence(row, wanted, default, bounds=bounds)


def row_by_document_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key in {str(row.get("document_id") or ""), str(row.get("id") or "")}:
            if key:
                by_id[key] = row
    return by_id


def pasted_tsv_for_match(row: dict[str, Any], token_start: int, token_stop: int) -> str:
    tokens = [str(token) for token in row.get("tokens") or []]
    labels = [str(label) for label in row.get("token_labels") or []]
    if token_start < 0 or token_stop > len(tokens) or token_stop <= token_start:
        raise ValueError(f"{row_id(row)}: token range {token_start}:{token_stop} is out of range")
    lines = [
        f"# doc_id = {row.get('id', row_id(row))}",
        f"# document_id = {row_id(row)}",
        "TOKEN\tNERTAG",
    ]
    for token, label in zip(tokens[token_start:token_stop], labels[token_start:token_stop], strict=True):
        lines.append(f"{token}\t{label}")
    return "\n".join(lines) + "\n"


def print_hit(lines: list[str], hit: tuple[int, int], *, index: int, total: int, context: int, query_tokens: list[str]) -> None:
    width = shutil.get_terminal_size((80, 24)).columns
    print(hit_title(index, total, hit_label_for_hit(lines, hit)))
    print("-" * width)
    print(build_block(lines, hit, context=context, query_tokens=query_tokens), end="")
    print("-" * width)


def review_hits(
    *,
    input_jsonl: Path,
    tsv_path: Path,
    candidates_path: Path,
    decisions_path: Path,
    audit_id: str,
    label: str,
    reviewer: str,
    token: str,
    token2: str | None = None,
    context: int = 6,
    only_o: bool = False,
    ignore_case: bool = True,
    label_metadata_paths: list[Path] | None = None,
    summary_json: Path | None = None,
) -> dict[str, Any]:
    lines = load_lines(tsv_path)
    hits = find_hits(lines, token, token2, only_o=only_o, ignore_case=ignore_case)
    rows = load_jsonl(input_jsonl)
    rows_by_id = row_by_document_id(rows)
    label_metadata = review_ui.load_label_metadata(label_metadata_paths or [])
    query_tokens = [token, *([token2] if token2 else [])]
    accepted = 0
    skipped = 0
    index = 0
    while hits:
        hit = hits[index]
        current = tsv_hit(lines, hit)
        row = rows_by_id.get(current.document_id)
        if row is None:
            raise ValueError(f"source document not found for TSV hit: {current.document_id}")
        print_hit(lines, hit, index=index + 1, total=len(hits), context=context, query_tokens=query_tokens)
        command = input("[Enter/n] next, [p] previous, [a] annotate, [s] skip, [q] quit: ").strip().lower()
        if command in {"q", "quit"}:
            break
        if command in {"p", "prev", "previous"}:
            index = max(0, index - 1)
            continue
        if command in {"s", "skip"}:
            skipped += 1
            index += 1
        elif command in {"a", "annotate"}:
            bounds = visible_token_bounds(lines, hit, context=context)
            while True:
                try:
                    token_start, token_stop = read_annotation_span(row, (current.token_start, current.token_stop), bounds=bounds)
                except ValueError as exc:
                    print(exc)
                    continue
                break
            raw_label = input(f"label [{label}]: ").strip() or label
            match = Match(row=row, token_start=token_start, token_stop=token_stop)
            summary = build_accepted_patches(
                input_jsonl=input_jsonl,
                candidates_path=candidates_path,
                decisions_path=decisions_path,
                audit_id=audit_id,
                label=raw_label,
                pasted_tsv=pasted_tsv_for_match(row, token_start, token_stop),
                reviewer=reviewer,
                label_metadata=label_metadata,
                selected_matches=[match],
                include_existing=True,
            )
            accepted += int(summary["new_decisions"])
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            index += 1
        else:
            index += 1
        if index >= len(hits):
            break
    result = {
        "accepted": accepted,
        "audit_id": audit_id,
        "candidates": str(candidates_path),
        "decisions": str(decisions_path),
        "hits": len(hits),
        "label": label,
        "skipped": skipped,
        "tsv": str(tsv_path),
    }
    if summary_json:
        summary_json.parent.mkdir(parents=True, exist_ok=True)
        summary_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review TSV search hits and create accepted span-patch audit decisions.")
    parser.add_argument("--input-jsonl", required=True, type=Path)
    parser.add_argument("--tsv", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--search", required=True)
    parser.add_argument("--search2")
    parser.add_argument("--context", type=int, default=6)
    parser.add_argument("--only-O", action="store_true")
    parser.add_argument("--case-sensitive", action="store_true")
    parser.add_argument("--label-metadata", action="append", type=Path, default=[])
    parser.add_argument("--summary-json", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    review_hits(
        input_jsonl=args.input_jsonl,
        tsv_path=args.tsv,
        candidates_path=args.candidates,
        decisions_path=args.decisions,
        audit_id=args.audit_id,
        label=args.label,
        reviewer=args.reviewer,
        token=args.search,
        token2=args.search2,
        context=args.context,
        only_o=args.only_O,
        ignore_case=not args.case_sensitive,
        label_metadata_paths=args.label_metadata,
        summary_json=args.summary_json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
