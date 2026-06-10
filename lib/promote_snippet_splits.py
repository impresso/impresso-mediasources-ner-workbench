"""Promote exported snippet JSONL rows into committed dataset splits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SPLITS = ("train", "validation", "test")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def row_id(row: dict[str, Any]) -> str:
    value = row.get("document_id") or row.get("id")
    if value is None:
        raise ValueError(f"Row has neither document_id nor id: {row}")
    return str(value)


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row_id(row).casefold(), row_id(row)))


def promote_split(base_path: Path, snippet_paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_rows = load_jsonl(base_path)
    rows_by_id = {row_id(row): row for row in base_rows}
    snippet_rows = []
    duplicate_snippet_ids = set()
    seen_snippet_ids = set()

    for path in snippet_paths:
        for row in load_jsonl(path):
            rid = row_id(row)
            if rid in seen_snippet_ids:
                duplicate_snippet_ids.add(rid)
            seen_snippet_ids.add(rid)
            snippet_rows.append(row)

    replaced = 0
    added = 0
    for row in snippet_rows:
        rid = row_id(row)
        if rid in rows_by_id:
            replaced += 1
        else:
            added += 1
        rows_by_id[rid] = row

    promoted_rows = sort_rows(list(rows_by_id.values()))
    summary = {
        "base_rows": len(base_rows),
        "snippet_rows": len(snippet_rows),
        "added": added,
        "replaced": replaced,
        "duplicate_snippet_ids": sorted(duplicate_snippet_ids),
        "output_rows": len(promoted_rows),
    }
    return promoted_rows, summary


def collect_snippet_targets(snippet_paths: dict[str, list[Path]]) -> tuple[dict[str, str], dict[str, list[str]]]:
    targets: dict[str, str] = {}
    duplicates: dict[str, set[str]] = {}
    for split in SPLITS:
        for path in snippet_paths.get(split, []):
            for row in load_jsonl(path):
                rid = row_id(row)
                previous = targets.get(rid)
                if previous is None:
                    targets[rid] = split
                    continue
                duplicates.setdefault(rid, {previous}).add(split)
    return targets, {rid: sorted(splits) for rid, splits in sorted(duplicates.items())}


def drop_refreshed_snippets_from_old_splits(
    rows_by_split: dict[str, list[dict[str, Any]]],
    snippet_targets: dict[str, str],
) -> dict[str, int]:
    removed = {split: 0 for split in SPLITS}
    for split, rows in rows_by_split.items():
        kept = []
        for row in rows:
            target_split = snippet_targets.get(row_id(row))
            if target_split is not None and target_split != split:
                removed[split] += 1
                continue
            kept.append(row)
        rows_by_split[split] = kept
    return removed


def duplicate_ids_across_splits(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    seen: dict[str, str] = {}
    duplicates: dict[str, set[str]] = {}
    for split in SPLITS:
        for row in rows_by_split.get(split, []):
            rid = row_id(row)
            previous = seen.get(rid)
            if previous is None:
                seen[rid] = split
                continue
            duplicates.setdefault(rid, {previous}).add(split)
    return {rid: sorted(splits) for rid, splits in sorted(duplicates.items())}


def parse_split_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"Expected SPLIT=PATH, got {value!r}")
    split, path = value.split("=", 1)
    if split not in SPLITS:
        raise argparse.ArgumentTypeError(f"Unknown split {split!r}; expected one of {', '.join(SPLITS)}")
    return split, Path(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote exported snippet rows into dataset JSONL splits.")
    parser.add_argument("--base", action="append", type=parse_split_path, required=True, help="Base split as SPLIT=PATH. Can be repeated.")
    parser.add_argument("--snippet", action="append", type=parse_split_path, default=[], help="Snippet split as SPLIT=PATH. Can be repeated.")
    parser.add_argument("--output", action="append", type=parse_split_path, help="Output split as SPLIT=PATH. Defaults to in-place base paths.")
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Summarize the promotion without writing outputs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_paths = dict(args.base)
    snippet_paths: dict[str, list[Path]] = {split: [] for split in SPLITS}
    for split, path in args.snippet:
        snippet_paths[split].append(path)
    output_paths = dict(args.output or args.base)
    snippet_targets, duplicate_snippet_ids_across_splits = collect_snippet_targets(snippet_paths)

    summary: dict[str, Any] = {"dry_run": bool(args.dry_run), "splits": {}}
    summary["duplicate_snippet_ids_across_splits"] = duplicate_snippet_ids_across_splits
    if duplicate_snippet_ids_across_splits and not args.dry_run:
        examples = []
        for rid, splits in list(duplicate_snippet_ids_across_splits.items())[:10]:
            examples.append(f"{rid} ({', '.join(splits)})")
        more = "" if len(duplicate_snippet_ids_across_splits) <= 10 else " ..."
        raise ValueError(
            "duplicate snippet document_id values across exported snippet splits: "
            + "; ".join(examples)
            + more
        )

    promoted_by_split: dict[str, list[dict[str, Any]]] = {}
    for split in SPLITS:
        if split not in base_paths:
            continue
        if split not in output_paths:
            raise ValueError(f"Missing output path for split {split!r}")
        promoted_rows, split_summary = promote_split(base_paths[split], snippet_paths[split])
        promoted_by_split[split] = promoted_rows
        if split_summary["duplicate_snippet_ids"] and not args.dry_run:
            duplicates = ", ".join(split_summary["duplicate_snippet_ids"][:10])
            more = "" if len(split_summary["duplicate_snippet_ids"]) <= 10 else " ..."
            raise ValueError(
                f"{split}: duplicate snippet document_id values in exported snippet files: {duplicates}{more}. "
                "Re-run the snippet export targets to produce unique exported IDs before promotion."
            )
        split_summary.update(
            {
                "base_path": str(base_paths[split]),
                "snippet_paths": [str(path) for path in snippet_paths[split]],
                "output_path": str(output_paths[split]),
            }
        )
        summary["splits"][split] = split_summary

    removed_refreshed = drop_refreshed_snippets_from_old_splits(promoted_by_split, snippet_targets)
    for split, count in removed_refreshed.items():
        if split in summary["splits"]:
            summary["splits"][split]["removed_refreshed_from_old_split"] = count
            summary["splits"][split]["output_rows"] = len(promoted_by_split[split])

    cross_split_duplicates = duplicate_ids_across_splits(promoted_by_split)
    summary["duplicate_document_ids_across_splits"] = cross_split_duplicates
    if cross_split_duplicates and not args.dry_run:
        examples = []
        for rid, splits in list(cross_split_duplicates.items())[:10]:
            examples.append(f"{rid} ({', '.join(splits)})")
        more = "" if len(cross_split_duplicates) <= 10 else " ..."
        raise ValueError(
            "duplicate document_id values across train/validation/test splits: "
            + "; ".join(examples)
            + more
        )

    for split, promoted_rows in promoted_by_split.items():
        if not args.dry_run:
            write_jsonl(output_paths[split], promoted_rows)

    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
