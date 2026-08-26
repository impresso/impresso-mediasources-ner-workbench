from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .promote_snippet_splits import SPLITS, row_id


def load_jsonl_with_locations(split: str, path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append({"split": split, "path": str(path), "line": line_number, "row": row})
    return rows


def split_rows(paths: dict[str, Path]) -> dict[str, list[dict[str, Any]]]:
    return {split: [located["row"] for located in load_jsonl_with_locations(split, path)] for split, path in paths.items()}


def duplicate_locations(paths: dict[str, Path]) -> dict[str, list[dict[str, Any]]]:
    locations_by_id: dict[str, list[dict[str, Any]]] = {}
    for split in SPLITS:
        path = paths.get(split)
        if path is None:
            continue
        for located in load_jsonl_with_locations(split, path):
            locations_by_id.setdefault(row_id(located["row"]), []).append(
                {
                    "split": located["split"],
                    "path": located["path"],
                    "line": located["line"],
                    "source_component": located["row"].get("source_component", ""),
                    "row_split": located["row"].get("split", ""),
                }
            )
    return {
        rid: sorted(locations, key=lambda item: SPLITS.index(item["split"]))
        for rid, locations in sorted(locations_by_id.items())
        if len({location["split"] for location in locations}) > 1
    }


def load_current_targets(paths: list[tuple[str, Path]]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for split, path in paths:
        for located in load_jsonl_with_locations(split, path):
            targets[row_id(located["row"])] = split
    return targets


def removal_hints(duplicates: dict[str, list[dict[str, Any]]], *, current_targets: dict[str, str] | None = None) -> list[dict[str, Any]]:
    current_targets = current_targets or {}
    hints = []
    for rid, locations in duplicates.items():
        target_split = current_targets.get(rid)
        target_matches = [location for location in locations if location.get("split") == target_split] if target_split else []
        matching = target_matches or [location for location in locations if location.get("row_split") == location.get("split")]
        keep = matching[0] if matching else locations[-1]
        remove = [location for location in locations if location is not keep]
        hints.append(
            {
                "document_id": rid,
                "keep": keep,
                "remove": remove,
                "reason": f"keep {keep['split']} copy; remove duplicate row(s) from other split file(s)",
            }
        )
    return hints


def validate_splits(paths: dict[str, Path], *, current_targets: dict[str, str] | None = None) -> dict[str, Any]:
    rows_by_split = split_rows(paths)
    duplicates = duplicate_locations(paths)
    return {
        "rows": {split: len(rows_by_split.get(split, [])) for split in SPLITS if split in paths},
        "duplicate_document_ids_across_splits": {rid: [location["split"] for location in locations] for rid, locations in duplicates.items()},
        "duplicate_locations": duplicates,
        "removal_hints": removal_hints(duplicates, current_targets=current_targets),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate dataset train/validation/test split integrity.")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument(
        "--snippet",
        action="append",
        default=[],
        metavar="SPLIT=PATH",
        help="Optional exported snippet split used to choose which duplicate copy to keep. Can be repeated.",
    )
    parser.add_argument("--summary-json", type=Path)
    return parser.parse_args(argv)


def parse_split_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"Expected SPLIT=PATH, got {value!r}")
    split, path = value.split("=", 1)
    if split not in SPLITS:
        raise argparse.ArgumentTypeError(f"Unknown split {split!r}; expected one of {', '.join(SPLITS)}")
    return split, Path(path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    snippet_paths = [parse_split_path(value) for value in args.snippet]
    summary = validate_splits(
        {"train": args.train, "validation": args.validation, "test": args.test},
        current_targets=load_current_targets(snippet_paths),
    )
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    duplicates = summary["duplicate_document_ids_across_splits"]
    if duplicates:
        examples = []
        for rid, splits in list(duplicates.items())[:10]:
            examples.append(f"{rid} ({', '.join(splits)})")
        more = "" if len(duplicates) <= 10 else " ..."
        print(
            "duplicate document_id values across train/validation/test splits: " + "; ".join(examples) + more,
            file=sys.stderr,
        )
        print("Suggested cleanup:", file=sys.stderr)
        for hint in summary["removal_hints"][:10]:
            keep = hint["keep"]
            print(f"  keep {keep['path']}:{keep['line']} ({keep['split']}) for {hint['document_id']}", file=sys.stderr)
            for remove in hint["remove"]:
                print(f"  remove {remove['path']}:{remove['line']} ({remove['split']}) for {hint['document_id']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
