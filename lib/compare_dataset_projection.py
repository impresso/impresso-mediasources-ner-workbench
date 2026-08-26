from __future__ import annotations

import argparse
import filecmp
import json
from pathlib import Path
from typing import Any


DEFAULT_COMPARISONS = (
    ("data/train.jsonl", "train.jsonl"),
    ("data/validation.jsonl", "validation.jsonl"),
    ("data/test.jsonl", "test.jsonl"),
    ("label_map.json", "label_map.json"),
)


def parse_comparison(value: str) -> tuple[str, str]:
    if "=" in value:
        left, right = value.split("=", 1)
        left = left.strip()
        right = right.strip()
    else:
        left = right = value.strip()
    if not left or not right:
        raise ValueError(f"invalid comparison mapping: {value!r}")
    return left, right


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def public_projection(row: dict[str, Any]) -> dict[str, Any]:
    projected = dict(row)
    projected.pop("legacy", None)
    if "entities" in projected:
        projected["entities"] = [
            {key: value for key, value in entity.items() if key not in {"status", "ocr_correction"}}
            for entity in projected["entities"]
        ]
    return projected


def compare_jsonl_projection(hf_path: Path, git_path: Path) -> dict[str, Any]:
    hf_rows = load_jsonl(hf_path)
    git_rows = load_jsonl(git_path)
    row_count = min(len(hf_rows), len(git_rows))
    differences = []
    for index, (hf_row, git_row) in enumerate(zip(hf_rows, git_rows, strict=False)):
        projected = public_projection(git_row)
        if hf_row != projected:
            differences.append(
                {
                    "document_id": hf_row.get("document_id") or hf_row.get("id"),
                    "index": index,
                    "status": "projection_differs",
                }
            )
    if len(hf_rows) != len(git_rows):
        differences.append({"git_rows": len(git_rows), "hf_rows": len(hf_rows), "status": "row_count_differs"})
    return {
        "differences": differences[:20],
        "git_rows": len(git_rows),
        "hf_rows": len(hf_rows),
        "projected_matches": row_count - sum(1 for item in differences if item["status"] == "projection_differs"),
        "projected_differences": len(differences),
    }


def is_jsonl_mapping(hf_name: str, git_name: str) -> bool:
    return hf_name.endswith(".jsonl") and git_name.endswith(".jsonl")


def compare_files(*, hf_dir: Path, git_dir: Path, comparisons: list[tuple[str, str]]) -> dict:
    results = []
    errors = []
    for hf_name, git_name in comparisons:
        hf_path = hf_dir / hf_name
        git_path = git_dir / git_name
        item = {
            "git_file": git_name,
            "hf_file": hf_name,
            "git_path": str(git_path),
            "hf_path": str(hf_path),
        }
        if not hf_path.is_file():
            item["status"] = "missing_hf"
            errors.append(item)
        elif not git_path.is_file():
            item["status"] = "missing_git"
            errors.append(item)
        elif is_jsonl_mapping(hf_name, git_name):
            projection = compare_jsonl_projection(hf_path, git_path)
            item.update(projection)
            if projection["projected_differences"]:
                item["status"] = "projection_differs"
                errors.append(item)
            else:
                item["status"] = "projection_match"
        elif filecmp.cmp(hf_path, git_path, shallow=False):
            item["status"] = "match"
        else:
            item["status"] = "differs"
            errors.append(item)
        results.append(item)
    return {"comparisons": results, "errors": errors, "ok": not errors}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare a local HF dataset materialization with a Git release snapshot.")
    parser.add_argument("--hf-dir", type=Path, required=True)
    parser.add_argument("--git-dir", type=Path, required=True)
    parser.add_argument(
        "--compare",
        action="append",
        default=[],
        help="File mapping as HF_PATH=GIT_PATH. May be repeated. Defaults to data/*.jsonl and label_map.json.",
    )
    parser.add_argument("--summary-json", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    comparisons = [parse_comparison(value) for value in args.compare] if args.compare else list(DEFAULT_COMPARISONS)
    summary = compare_files(hf_dir=args.hf_dir, git_dir=args.git_dir, comparisons=comparisons)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
