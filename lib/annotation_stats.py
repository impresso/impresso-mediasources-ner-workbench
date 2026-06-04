from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .snippet_data import load_jsonl


DEFAULT_SOURCES = {
    "legacy": [
        Path("data/curated/legacy-import/train.jsonl"),
        Path("data/curated/legacy-import/validation.jsonl"),
        Path("data/curated/legacy-import/test.jsonl"),
    ],
    "newsagency_snippets": [Path("data/curated/snippets/newsagencies/train.jsonl")],
    "radiostation_snippets": [Path("data/curated/snippets/radiostations/train.jsonl")],
}


def load_metadata(paths: list[Path]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.is_file():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            label = str(row.get("label") or "")
            if not label.startswith("org.ent."):
                continue
            metadata[label] = {
                "label": label,
                "canonical_id": row.get("canonical_id") or label.rsplit(".", 1)[-1],
                "display_name": row.get("display_name") or label,
                "family": family_for_label(label),
                "trainable": bool(row.get("trainable", True)),
            }
    return metadata


def family_for_label(label: str) -> str:
    if label.startswith("org.ent.radiostation."):
        return "radiostation"
    if label.startswith("org.ent.pressagency."):
        return "pressagency"
    return "other"


def count_training_file(path: Path) -> tuple[Counter[str], int, int]:
    counts: Counter[str] = Counter()
    rows = 0
    entities = 0
    if not path.is_file():
        return counts, rows, entities
    for row in load_jsonl(path):
        rows += 1
        for entity in row.get("entities") or []:
            label = str(entity.get("label") or "")
            if label.startswith("org.ent."):
                counts[label] += 1
                entities += 1
    return counts, rows, entities


def count_review_file(path: Path) -> tuple[Counter[str], Counter[str]]:
    statuses: Counter[str] = Counter()
    pending_by_label: Counter[str] = Counter()
    if not path.is_file():
        return statuses, pending_by_label
    for row in load_jsonl(path):
        curation = row.get("curation") or {}
        status = str(curation.get("status") or "")
        if not status:
            continue
        statuses[status] += 1
        if status == "needs_review":
            label = str(curation.get("label") or row.get("candidate_label") or "")
            if label.startswith("org.ent."):
                pending_by_label[label] += 1
    return statuses, pending_by_label


def merge_counter(target: Counter[str], source: Counter[str]) -> None:
    for key, value in source.items():
        target[key] += value


def build_stats(args: argparse.Namespace) -> dict[str, Any]:
    metadata = load_metadata(args.label_metadata)
    labels = set(metadata)
    by_source: dict[str, Counter[str]] = {}
    source_rows: dict[str, int] = {}
    source_entities: dict[str, int] = {}
    total_counts: Counter[str] = Counter()

    sources = {
        "legacy": args.legacy_jsonl,
        "newsagency_snippets": args.newsagency_snippet_jsonl,
        "radiostation_snippets": args.radiostation_snippet_jsonl,
    }
    for source_name, paths in sources.items():
        source_counts: Counter[str] = Counter()
        rows = 0
        entities = 0
        for path in paths:
            counts, file_rows, file_entities = count_training_file(path)
            merge_counter(source_counts, counts)
            rows += file_rows
            entities += file_entities
        by_source[source_name] = source_counts
        source_rows[source_name] = rows
        source_entities[source_name] = entities
        merge_counter(total_counts, source_counts)
        labels.update(source_counts)

    review_statuses: dict[str, dict[str, int]] = {}
    pending_by_label: Counter[str] = Counter()
    for source_name, path in {
        "newsagency_snippets": args.newsagency_reviewed_jsonl,
        "radiostation_snippets": args.radiostation_reviewed_jsonl,
    }.items():
        statuses, pending = count_review_file(path)
        review_statuses[source_name] = dict(sorted(statuses.items()))
        merge_counter(pending_by_label, pending)
        labels.update(pending)

    rows_out = []
    for label in sorted(labels):
        total = total_counts[label]
        missing = max(args.target_per_label - total, 0)
        rows_out.append(
            {
                "label": label,
                "family": metadata.get(label, {}).get("family") or family_for_label(label),
                "canonical_id": metadata.get(label, {}).get("canonical_id") or label.rsplit(".", 1)[-1],
                "display_name": metadata.get(label, {}).get("display_name") or label,
                "legacy": by_source["legacy"][label],
                "newsagency_snippets": by_source["newsagency_snippets"][label],
                "radiostation_snippets": by_source["radiostation_snippets"][label],
                "total": total,
                "target": args.target_per_label,
                "missing_to_target": missing,
                "pending_review": pending_by_label[label],
            }
        )

    summary = {
        "target_per_label": args.target_per_label,
        "sources": {
            source: {"rows": source_rows[source], "entities": source_entities[source]}
            for source in sorted(source_rows)
        },
        "review_statuses": review_statuses,
        "labels_total": len(rows_out),
        "labels_below_target": sum(1 for row in rows_out if row["missing_to_target"] > 0),
        "rows": rows_out,
    }
    return summary


def print_table(rows: list[dict[str, Any]], *, limit: int, family: str) -> None:
    selected = [row for row in rows if family == "all" or row["family"] == family]
    selected.sort(key=lambda row: (row["missing_to_target"] == 0, row["total"], row["label"]))
    if limit > 0:
        selected = selected[:limit]
    headers = ["label", "legacy", "news", "radio", "total", "missing", "pending"]
    widths = {
        "label": max([len("label"), *(len(row["label"]) for row in selected)] or [5]),
        "legacy": 6,
        "news": 5,
        "radio": 5,
        "total": 5,
        "missing": 7,
        "pending": 7,
    }
    print(
        f"{headers[0]:<{widths['label']}}  "
        f"{headers[1]:>{widths['legacy']}}  "
        f"{headers[2]:>{widths['news']}}  "
        f"{headers[3]:>{widths['radio']}}  "
        f"{headers[4]:>{widths['total']}}  "
        f"{headers[5]:>{widths['missing']}}  "
        f"{headers[6]:>{widths['pending']}}"
    )
    print("-" * (widths["label"] + 48))
    for row in selected:
        print(
            f"{row['label']:<{widths['label']}}  "
            f"{row['legacy']:>{widths['legacy']}}  "
            f"{row['newsagency_snippets']:>{widths['news']}}  "
            f"{row['radiostation_snippets']:>{widths['radio']}}  "
            f"{row['total']:>{widths['total']}}  "
            f"{row['missing_to_target']:>{widths['missing']}}  "
            f"{row['pending_review']:>{widths['pending']}}"
        )


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "family",
        "label",
        "canonical_id",
        "display_name",
        "legacy",
        "newsagency_snippets",
        "radiostation_snippets",
        "total",
        "target",
        "missing_to_target",
        "pending_review",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize media-source annotation coverage by label.")
    parser.add_argument("--target-per-label", type=int, default=20)
    parser.add_argument("--label-metadata", type=Path, action="append", default=[])
    parser.add_argument("--legacy-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--newsagency-snippet-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--radiostation-snippet-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--newsagency-reviewed-jsonl", type=Path, default=Path("data/curated/snippets/newsagencies/reviewed.jsonl"))
    parser.add_argument("--radiostation-reviewed-jsonl", type=Path, default=Path("data/curated/snippets/radiostations/reviewed.jsonl"))
    parser.add_argument("--family", choices=["all", "pressagency", "radiostation"], default="all")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--tsv-output", type=Path)
    return parser.parse_args(argv)


def fill_defaults(args: argparse.Namespace) -> argparse.Namespace:
    if not args.label_metadata:
        args.label_metadata = [Path("resources/newsagency_seeds.json"), Path("resources/radiostation_seeds.json")]
    if not args.legacy_jsonl:
        args.legacy_jsonl = DEFAULT_SOURCES["legacy"]
    if not args.newsagency_snippet_jsonl:
        args.newsagency_snippet_jsonl = DEFAULT_SOURCES["newsagency_snippets"]
    if not args.radiostation_snippet_jsonl:
        args.radiostation_snippet_jsonl = DEFAULT_SOURCES["radiostation_snippets"]
    return args


def main(argv: list[str] | None = None) -> int:
    args = fill_defaults(parse_args(argv))
    summary = build_stats(args)
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, ensure_ascii=False, sort_keys=True))
    print_table(summary["rows"], limit=args.limit, family=args.family)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.tsv_output:
        write_tsv(args.tsv_output, summary["rows"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
