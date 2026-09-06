from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .snippet_data import load_jsonl, write_jsonl


def base_document_id(value: Any) -> str:
    return str(value or "").split("#", 1)[0]


def row_document_id(row: dict[str, Any]) -> str:
    for field in ("document_id", "sample_document_id", "content_item_id", "ci_id"):
        value = row.get(field)
        if value:
            return base_document_id(value)
    source = row.get("source")
    if isinstance(source, dict) and source.get("document_id"):
        return base_document_id(source["document_id"])
    legacy = row.get("legacy")
    if isinstance(legacy, dict) and legacy.get("source_document_id"):
        return base_document_id(legacy["source_document_id"])
    row_id = str(row.get("id") or "")
    for prefix in ("cookbook-snippet:", "snippet:", "newsagency-snippet:", "radiostation-snippet:", "newspaper-snippet:"):
        if row_id.startswith(prefix):
            return base_document_id(row_id.removeprefix(prefix))
    return base_document_id(row_id)


def parse_source(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("source must be role=path")
    role, path = value.split("=", 1)
    role = role.strip()
    if not role:
        raise argparse.ArgumentTypeError("source role must not be empty")
    return role, Path(path)


def collect_article_ids(sources: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for role, path in sources:
        for row in load_jsonl(path):
            document_id = row_document_id(row)
            if not document_id:
                continue
            by_id[document_id].append({"role": role, "path": str(path)})
    return [
        {
            "content_item_id": document_id,
            "sources": sorted(provenance, key=lambda item: (item["role"], item["path"])),
        }
        for document_id, provenance in sorted(by_id.items())
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export content-item IDs already present in dataset or curation files.")
    parser.add_argument("--source", type=parse_source, action="append", default=[], help="Input JSONL as role=path.")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = collect_article_ids(args.source)
    write_jsonl(args.output, rows)
    print(json.dumps({"output": str(args.output), "rows": len(rows)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
