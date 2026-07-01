from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

SPLITS = ("train", "validation", "test")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def entity_family(label: str) -> str:
    if ".pressagency." in label:
        return "press agency"
    if ".radiostation." in label:
        return "radio station"
    return "other"


def collect_statistics(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    split_stats = {}
    languages = {split: Counter() for split in SPLITS}
    families = {split: Counter() for split in SPLITS}
    labels = {split: Counter() for split in SPLITS}
    document_splits: dict[str, set[str]] = {}

    for split in SPLITS:
        rows = rows_by_split.get(split, [])
        newspapers: set[str] = set()
        dates: list[str] = []
        tokens = mentions = annotated_documents = 0
        for row in rows:
            entities = row.get("entities") or []
            tokens += len(row.get("tokens") or [])
            mentions += len(entities)
            annotated_documents += bool(entities)
            languages[split][str(row.get("language") or "unknown")] += 1
            if row.get("newspaper"):
                newspapers.add(str(row["newspaper"]))
            if row.get("date"):
                dates.append(str(row["date"])[:10])
            document_id = str(row.get("document_id") or row.get("id") or "")
            if document_id:
                document_splits.setdefault(document_id, set()).add(split)
            for entity in entities:
                label = str(entity.get("label") or "unknown")
                labels[split][label] += 1
                families[split][entity_family(label)] += 1
        split_stats[split] = {
            "documents": len(rows),
            "annotated_documents": annotated_documents,
            "tokens": tokens,
            "mentions": mentions,
            "newspapers": len(newspapers),
            "date_start": min(dates) if dates else None,
            "date_end": max(dates) if dates else None,
        }

    return {
        "splits": split_stats,
        "languages": {split: dict(sorted(value.items())) for split, value in languages.items()},
        "families": {split: dict(sorted(value.items())) for split, value in families.items()},
        "labels": {split: dict(sorted(value.items())) for split, value in labels.items()},
        "duplicate_document_ids": {
            document_id: sorted(splits)
            for document_id, splits in sorted(document_splits.items())
            if len(splits) > 1
        },
    }


def number(value: int) -> str:
    return f"{value:,}"


def count_table(title: str, section: str, stats: dict[str, Any]) -> list[str]:
    names = sorted({name for split in SPLITS for name in stats[section][split]})
    lines = [f"## {title}", "", "| Value | Train | Validation | Test | Total |", "|---|---:|---:|---:|---:|"]
    for name in names:
        counts = [int(stats[section][split].get(name, 0)) for split in SPLITS]
        lines.append(f"| `{name}` | {number(counts[0])} | {number(counts[1])} | {number(counts[2])} | {number(sum(counts))} |")
    return [*lines, ""]


def render_markdown(stats: dict[str, Any], *, release: str) -> str:
    lines = [
        f"# Dataset Statistics: {release}",
        "",
        "This report is generated from the released train, validation, and test JSONL files.",
        "",
        "## Overview",
        "",
        "| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for split in SPLITS:
        item = stats["splits"][split]
        lines.append(
            f"| {split} | {number(item['documents'])} | {number(item['annotated_documents'])} | "
            f"{number(item['tokens'])} | {number(item['mentions'])} | {number(item['newspapers'])} | "
            f"{item['date_start'] or '-'} to {item['date_end'] or '-'} |"
        )
    totals = {key: sum(stats["splits"][split][key] for split in SPLITS) for key in ("documents", "annotated_documents", "tokens", "mentions")}
    lines.append(
        f"| **Total** | **{number(totals['documents'])}** | **{number(totals['annotated_documents'])}** | "
        f"**{number(totals['tokens'])}** | **{number(totals['mentions'])}** | - | - |"
    )
    lines.extend(["", "## Split Integrity", ""])
    duplicates = stats["duplicate_document_ids"]
    if duplicates:
        lines.append(f"Warning: {number(len(duplicates))} document IDs occur in more than one split.")
        lines.append("")
        lines.extend(f"- `{document_id}`: {', '.join(splits)}" for document_id, splits in duplicates.items())
    else:
        lines.append("No document IDs occur in more than one split.")
    lines.append("")
    lines.extend(count_table("Documents by Language", "languages", stats))
    lines.extend(count_table("Mentions by Entity Family", "families", stats))
    lines.extend(count_table("Mentions by Entity Label", "labels", stats))
    return "\n".join(lines).rstrip() + "\n"


def write_report(*, rows_by_split: dict[str, list[dict[str, Any]]], output: Path, release: str) -> dict[str, Any]:
    stats = collect_statistics(rows_by_split)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(stats, release=release), encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Markdown statistics report for dataset splits.")
    for split in SPLITS:
        parser.add_argument(f"--{split}", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release", default="unreleased")
    args = parser.parse_args(argv)
    rows_by_split = {split: load_jsonl(Path(getattr(args, split))) for split in SPLITS}
    stats = write_report(rows_by_split=rows_by_split, output=Path(args.output), release=args.release)
    print(json.dumps({"output": args.output, "splits": stats["splits"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
