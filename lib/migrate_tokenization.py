from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .snippet_data import load_jsonl, write_jsonl
from .tokenization import (
    TOKENIZATION_PROFILE,
    bio_to_character_entities,
    narrow_french_agence,
    project_entities_to_bio,
    tokenize_with_offsets,
    validate_canonical_tokens,
)


def migrate_row(row: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row_id = str(row.get("id") or row.get("document_id") or "<missing-id>")
    text = str(row["text"])
    old_tokens = [str(token) for token in row["tokens"]]
    old_entities = bio_to_character_entities(row)
    changes: list[dict[str, Any]] = []
    migrated_entities = []
    for entity in old_entities:
        migrated, narrowed = narrow_french_agence(entity, text)
        migrated_entities.append(migrated)
        if narrowed:
            changes.append(
                {
                    "id": row_id,
                    "kind": "exclude_french_elided_article",
                    "label": entity.label,
                    "old_start": entity.start,
                    "old_stop": entity.stop,
                    "old_surface": text[entity.start : entity.stop],
                    "new_start": migrated.start,
                    "new_stop": migrated.stop,
                    "new_surface": text[migrated.start : migrated.stop],
                }
            )
    tokens, starts, stops = tokenize_with_offsets(text)
    labels, entities = project_entities_to_bio(migrated_entities, starts, stops, row_id=row_id)
    old_metadata = {
        (int(entity.get("start", -1)), int(entity.get("stop", -1)), str(entity.get("label", ""))): entity
        for entity in row.get("entities", [])
        if isinstance(entity, dict)
    }
    materialized = []
    for entity in entities:
        source = old_metadata.get((entity["start"], entity["stop"], entity["label"]), {})
        if not source:
            source = next(
                (
                    candidate
                    for (start, stop, label), candidate in old_metadata.items()
                    if label == entity["label"] and start <= entity["start"] and stop >= entity["stop"]
                ),
                {},
            )
        item = dict(source)
        item.update(entity)
        item["surface"] = text[entity["start"] : entity["stop"]]
        item.setdefault("entity_family", entity["label"].split(".")[2] if entity["label"].count(".") >= 2 else "")
        item.setdefault("status", "accepted")
        materialized.append(item)
    migrated = dict(row)
    migrated["schema_version"] = "mediaagencies-jsonl-v0.2"
    migrated["tokenization"] = TOKENIZATION_PROFILE
    migrated["tokens"] = tokens
    migrated["token_start_offsets"] = starts
    migrated["token_end_offsets"] = stops
    migrated["token_labels"] = labels
    migrated["entities"] = materialized
    validate_canonical_tokens(text, tokens, starts, stops)
    if old_tokens != tokens:
        changes.append(
            {
                "id": row_id,
                "kind": "retokenized",
                "old_token_count": len(old_tokens),
                "new_token_count": len(tokens),
            }
        )
    return migrated, changes


def audit_split(path: Path, split: str) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    rows = load_jsonl(path)
    migrated_rows = []
    changes = []
    counters: Counter[str] = Counter()
    labels_before: Counter[str] = Counter()
    labels_after: Counter[str] = Counter()
    for row in rows:
        counters["rows"] += 1
        counters["tokens_before"] += len(row["tokens"])
        for entity in bio_to_character_entities(row):
            labels_before[entity.label] += 1
        try:
            migrated, row_changes = migrate_row(row)
        except ValueError as exc:
            row_id = str(row.get("id") or row.get("document_id") or "<missing-id>")
            migrated = row
            row_changes = [
                {
                    "id": row_id,
                    "kind": "tokenization_projection_error",
                    "error": str(exc),
                }
            ]
            counters["projection_error_rows"] += 1
        migrated_rows.append(migrated)
        changes.extend({"split": split, **change} for change in row_changes)
        counters["tokens_after"] += len(migrated["tokens"])
        if row["tokens"] != migrated["tokens"]:
            counters["retokenized_rows"] += 1
        if any(change["kind"] == "exclude_french_elided_article" for change in row_changes):
            counters["french_article_rows"] += 1
        for entity in bio_to_character_entities(migrated):
            labels_after[entity.label] += 1
    summary = {
        **dict(counters),
        "split": split,
        "input": str(path),
        "label_mentions_before": dict(sorted(labels_before.items())),
        "label_mentions_after": dict(sorted(labels_after.items())),
    }
    return migrated_rows, summary, changes


def render_markdown(profile: str, summaries: list[dict[str, Any]], changes: list[dict[str, Any]]) -> str:
    lines = [
        "# Tokenization Migration Audit",
        "",
        f"Target profile: `{profile}`",
        "",
        "| Split | Rows | Retokenized rows | Tokens before | Tokens after | French article rows |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summaries:
        lines.append(
        f"| {item['split']} | {item['rows']} | {item.get('retokenized_rows', 0)} | "
        f"{item['tokens_before']} | {item['tokens_after']} | {item.get('french_article_rows', 0)} |"
        )
    errors = [change for change in changes if change["kind"] == "tokenization_projection_error"]
    lines.extend(["", f"Rows with tokenization projection errors: **{len(errors)}**", ""])
    for change in errors:
        lines.append(f"- `{change['split']}:{change['id']}`: {change['error']}")
    narrowed = [change for change in changes if change["kind"] == "exclude_french_elided_article"]
    lines.extend(["", f"French elided-article boundaries narrowed: **{len(narrowed)}**", ""])
    for change in narrowed:
        lines.append(
            f"- `{change['split']}:{change['id']}`: `{change['old_surface']}` -> `{change['new_surface']}` "
            f"(`{change['label']}`)"
        )
    return "\n".join(lines) + "\n"


def parse_split(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or name not in {"train", "validation", "test"}:
        raise argparse.ArgumentTypeError("split must be train=PATH, validation=PATH, or test=PATH")
    return name, Path(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit or migrate JSONL to canonical punctuation tokenization.")
    parser.add_argument("--split", action="append", type=parse_split, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--changes-jsonl", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    return parser.parse_args(argv)


def write_lines(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    write_jsonl(path, rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summaries = []
    changes = []
    migrated_by_split = {}
    for split, path in args.split:
        migrated, summary, split_changes = audit_split(path, split)
        migrated_by_split[split] = migrated
        summaries.append(summary)
        changes.extend(split_changes)
    result = {"profile": TOKENIZATION_PROFILE, "splits": summaries, "changes": len(changes)}
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_lines(args.changes_jsonl, changes)
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text(render_markdown(TOKENIZATION_PROFILE, summaries, changes), encoding="utf-8")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for split, rows in migrated_by_split.items():
            write_jsonl(args.output_dir / f"{split}.jsonl", rows)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
