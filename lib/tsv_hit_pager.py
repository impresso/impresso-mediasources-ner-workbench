from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any, Iterable


RED = "\033[31;1m"
RESET = "\033[0m"


def is_token_line(line: str) -> bool:
    if not line.strip():
        return False
    if line.startswith("#"):
        return False
    if line.strip() == "--":
        return False
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 2:
        return False
    if parts[0] == "TOKEN" and parts[1] == "NERTAG":
        return False
    return True


def parse_token_line(line: str) -> tuple[str, str] | None:
    if not is_token_line(line):
        return None
    parts = line.rstrip("\n").split("\t")
    return parts[0], parts[1]


def token_matches(token: str, query: str, *, ignore_case: bool = True) -> bool:
    return token.casefold() == query.casefold() if ignore_case else token == query


def highlight_token_line(
    line: str,
    query_tokens: Iterable[str],
    *,
    ignore_case: bool = True,
    color: bool = True,
) -> str:
    parsed = parse_token_line(line)
    if parsed is None:
        return line
    token, _tag = parsed
    rest = line.rstrip("\n").split("\t")[1:]
    for query in query_tokens:
        if token_matches(token, query, ignore_case=ignore_case):
            if color:
                token = f"{RED}{token}{RESET}"
            break
    return "\t".join([token, *rest]) + "\n"


def find_hits(
    lines: list[str],
    query1: str,
    query2: str | None = None,
    *,
    only_o: bool = False,
    ignore_case: bool = True,
) -> list[tuple[int, int]]:
    hits: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        parsed = parse_token_line(line)
        if parsed is None:
            continue
        token, tag = parsed
        if query2 is None:
            if not token_matches(token, query1, ignore_case=ignore_case):
                continue
            if only_o and tag != "O":
                continue
            hits.append((index, index + 1))
            continue

        if index + 1 >= len(lines):
            continue
        parsed_next = parse_token_line(lines[index + 1])
        if parsed_next is None:
            continue
        token_next, tag_next = parsed_next
        if not token_matches(token, query1, ignore_case=ignore_case):
            continue
        if not token_matches(token_next, query2, ignore_case=ignore_case):
            continue
        if only_o and not (tag == "O" and tag_next == "O"):
            continue
        hits.append((index, index + 2))
    return hits


def is_document_start(line: str) -> bool:
    return line.startswith("# doc_id =")


def document_bounds(lines: list[str], hit: tuple[int, int]) -> tuple[int, int]:
    start, end = hit
    block_start = start
    while block_start > 0:
        previous = lines[block_start - 1]
        if not previous.strip():
            break
        block_start -= 1
        if is_document_start(lines[block_start]):
            break

    block_end = end
    while block_end < len(lines):
        line = lines[block_end]
        if not line.strip() or is_document_start(line):
            break
        block_end += 1
    return block_start, block_end


def metadata_for_hit(lines: list[str], hit: tuple[int, int]) -> dict[str, str]:
    document_start, _document_end = document_bounds(lines, hit)
    metadata: dict[str, str] = {}
    for index in range(document_start, hit[0] + 1):
        line = lines[index].strip()
        if not line.startswith("#"):
            continue
        key, separator, value = line[1:].strip().partition("=")
        if separator:
            metadata[key.strip()] = value.strip()
    return metadata


def document_id_for_hit(lines: list[str], hit: tuple[int, int]) -> str:
    metadata = metadata_for_hit(lines, hit)
    return metadata.get("document_id") or metadata.get("doc_id") or ""


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


def token_span_for_hit(lines: list[str], hit: tuple[int, int]) -> tuple[int, int]:
    return token_index_for_line(lines, hit, hit[0]), token_index_for_line(lines, hit, hit[1] - 1) + 1


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def row_by_document_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key in {str(row.get("document_id") or ""), str(row.get("id") or "")}:
            if key:
                by_id[key] = row
    return by_id


def overlaps(a_start: int, a_stop: int, b_start: int, b_stop: int) -> bool:
    return a_start < b_stop and b_start < a_stop


def hit_is_audited(lines: list[str], hit: tuple[int, int], rows_by_id: dict[str, dict[str, Any]]) -> bool:
    document_id = document_id_for_hit(lines, hit)
    row = rows_by_id.get(document_id)
    if row is None:
        return False
    token_start, token_stop = token_span_for_hit(lines, hit)
    starts = row.get("token_start_offsets") or []
    stops = row.get("token_end_offsets") or []
    if token_start < 0 or token_stop <= token_start or token_stop > len(starts) or token_stop > len(stops):
        return False
    start = int(starts[token_start])
    stop = int(stops[token_stop - 1])
    for mark in row.get("audit_marks") or []:
        if not isinstance(mark, dict) or mark.get("status") != "verified":
            continue
        try:
            mark_start = int(mark.get("start"))
            mark_stop = int(mark.get("stop"))
        except (TypeError, ValueError):
            continue
        if overlaps(start, stop, mark_start, mark_stop):
            return True
    return False


def filter_audited_hits(lines: list[str], hits: list[tuple[int, int]], *, source_jsonl: Path | None, include_audited: bool) -> list[tuple[int, int]]:
    if include_audited or source_jsonl is None:
        return hits
    rows_by_id = row_by_document_id(load_jsonl(source_jsonl))
    if not rows_by_id:
        return hits
    return [hit for hit in hits if not hit_is_audited(lines, hit, rows_by_id)]


def hit_label_for_hit(lines: list[str], hit: tuple[int, int]) -> str:
    metadata = metadata_for_hit(lines, hit)
    document_id = metadata.get("document_id") or metadata.get("doc_id") or ""
    split = metadata.get("split") or ""
    if document_id and split:
        return f"{document_id} [{split}]"
    return document_id or (f"[{split}]" if split else "")


def build_block(
    lines: list[str],
    hit: tuple[int, int],
    *,
    context: int,
    query_tokens: list[str],
    ignore_case: bool = True,
    color: bool = True,
) -> str:
    start, end = hit
    document_start, document_end = document_bounds(lines, hit)
    block_start = max(document_start, start - context)
    block_end = min(document_end, end + context)
    out: list[str] = []
    for index in range(block_start, block_end):
        if start <= index < end:
            out.append(highlight_token_line(lines[index], query_tokens, ignore_case=ignore_case, color=color))
        else:
            out.append(lines[index])
    return "".join(out)


def clear_screen() -> None:
    os.system("clear" if os.name != "nt" else "cls")


def hit_title(index: int, total: int, label: str = "") -> str:
    title = f"Hit {index}/{total}"
    return f"{title} {label}" if label else title


def page_hits(blocks: list[str], labels: list[str] | None = None) -> None:
    if not blocks:
        print("No matches.")
        return
    labels = labels or [""] * len(blocks)
    index = 0
    total = len(blocks)
    while True:
        clear_screen()
        width = shutil.get_terminal_size((80, 24)).columns
        print(hit_title(index + 1, total, labels[index]))
        print("-" * width)
        print(blocks[index], end="")
        print("-" * width)
        command = input("[Enter/n] next, [p] previous, [q] quit: ").strip().lower()
        if command in {"q", "quit"}:
            break
        if command in {"p", "prev", "previous"}:
            index = max(0, index - 1)
            continue
        if index + 1 >= total:
            break
        index += 1


def load_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search TSV token/tag files and show one colored hit block per screen.")
    parser.add_argument("file", type=Path, help="TSV file to search.")
    parser.add_argument("token", help="Token to search for.")
    parser.add_argument("token2", nargs="?", help="Optional adjacent second token.")
    parser.add_argument("-C", "--context", type=int, default=6, help="Context lines before and after the hit. Default: 6.")
    parser.add_argument("--only-O", action="store_true", help='Only match token lines whose tag is exactly "O".')
    parser.add_argument("--case-sensitive", action="store_true", help="Use case-sensitive matching.")
    parser.add_argument("--no-pager", action="store_true", help="Print all hit blocks separated by -- instead of paging.")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color highlighting.")
    parser.add_argument("--source-jsonl", type=Path, help="JSONL split used to suppress hits overlapping verified audit_marks.")
    parser.add_argument("--include-audited", action="store_true", help="Show hits overlapping verified audit_marks.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ignore_case = not args.case_sensitive
    query_tokens = [args.token]
    if args.token2 is not None:
        query_tokens.append(args.token2)
    lines = load_lines(args.file)
    hits = find_hits(lines, args.token, args.token2, only_o=args.only_O, ignore_case=ignore_case)
    hits = filter_audited_hits(lines, hits, source_jsonl=args.source_jsonl, include_audited=args.include_audited)
    labels = [hit_label_for_hit(lines, hit) for hit in hits]
    blocks = [
        build_block(
            lines,
            hit,
            context=args.context,
            query_tokens=query_tokens,
            ignore_case=ignore_case,
            color=not args.no_color,
        )
        for hit in hits
    ]
    if args.no_pager:
        if not blocks:
            print("No matches.")
            return 1
        for index, block in enumerate(blocks):
            if index:
                print("--")
            print(hit_title(index + 1, len(blocks), labels[index]))
            print(block, end="")
        return 0
    page_hits(blocks, labels)
    return 0 if blocks else 1


if __name__ == "__main__":
    raise SystemExit(main())
