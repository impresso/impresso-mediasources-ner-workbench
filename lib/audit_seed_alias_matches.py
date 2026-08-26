from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .audit_empty_training_docs import write_json, write_tsv
from .audit_missing_spans import load_jsonl, load_label_metadata, pattern_spans
from .score_radiostation_snippets import compact, high_precision_press_aliases, seed_aliases


TSV_COLUMNS = [
    "split",
    "document_id",
    "language",
    "date",
    "newspaper",
    "alias",
    "matcher",
    "predicted_label",
    "hit_token_start",
    "hit_token_stop",
    "hit_surface",
    "gold_label",
    "gold_token_start",
    "gold_token_stop",
    "gold_surface",
    "outcome",
    "boundary_delta",
    "left_context",
    "right_context",
]


def parse_split(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("split input must be NAME=PATH")
    name, path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("split name is empty")
    return name, Path(path)


def token_span(entity: dict[str, Any]) -> tuple[int, int] | None:
    start = entity.get("token_start")
    stop = entity.get("token_stop")
    if start is None or stop is None:
        return None
    return int(start), int(stop)


def overlaps(a_start: int, a_stop: int, b_start: int, b_stop: int) -> bool:
    return a_start < b_stop and a_stop > b_start


def token_boundary_delta(hit_start: int, hit_stop: int, gold_start: int, gold_stop: int) -> int:
    return abs(hit_start - gold_start) + abs(hit_stop - gold_stop)


def context(text: str, start: int, stop: int, radius: int) -> tuple[str, str]:
    return text[max(0, start - radius) : start].strip(), text[stop : min(len(text), stop + radius)].strip()


def seed_match_compacts(seed: dict[str, Any], label: str) -> tuple[tuple[str, int], ...]:
    aliases = high_precision_press_aliases(seed) if label.startswith("org.ent.pressagency.") else seed_aliases(seed)
    values = []
    for alias in aliases:
        value = compact(str(alias))
        if value:
            token_len = len(re.findall(r"\w+|[^\w\s]", str(alias), flags=re.UNICODE))
            values.append((value, max(1, token_len)))
    seen = set()
    return tuple(value for value in values if not (value in seen or seen.add(value)))


def document_compact_windows(tokens: list[str], max_width: int) -> set[str]:
    values = [compact(token) for token in tokens]
    out = set(values)
    for start in range(len(values)):
        current = ""
        for stop in range(start, min(len(values), start + max_width)):
            current += values[stop]
            if current:
                out.add(current)
    return out


def seed_possible_in_document(windows: set[str], alias_compacts: tuple[tuple[str, int], ...]) -> bool:
    for alias, _token_len in alias_compacts:
        if alias in windows:
            return True
    return False


def closest_gold_match(row: dict[str, Any], hit: dict[str, Any]) -> tuple[dict[str, Any] | None, str, int | None]:
    hit_start = int(hit["token_start"])
    hit_stop = int(hit["token_stop"])
    hit_label = str(hit["label"])
    overlapping = []
    same_label = []
    for entity in row.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        span = token_span(entity)
        if span is None:
            continue
        gold_start, gold_stop = span
        if not overlaps(hit_start, hit_stop, gold_start, gold_stop):
            continue
        delta = token_boundary_delta(hit_start, hit_stop, gold_start, gold_stop)
        overlapping.append((delta, entity))
        if str(entity.get("label") or "") == hit_label:
            same_label.append((delta, entity))

    for delta, entity in same_label:
        gold_start, gold_stop = token_span(entity) or (-1, -1)
        if hit_start == gold_start and hit_stop == gold_stop:
            return entity, "exact", 0
    if same_label:
        delta, entity = min(same_label, key=lambda item: item[0])
        return entity, "same_label_overlap", delta
    if overlapping:
        delta, entity = min(overlapping, key=lambda item: item[0])
        return entity, "label_conflict", delta
    return None, "false_positive", None


def audit_row(
    split: str,
    row: dict[str, Any],
    metadata: dict[str, dict[str, Any]],
    alias_compacts: dict[str, tuple[tuple[str, int], ...]],
    *,
    context_chars: int,
) -> list[dict[str, Any]]:
    rows = []
    doc_id = str(row.get("id") or row.get("document_id") or "")
    text = str(row.get("text") or "")
    tokens = [str(token) for token in row.get("tokens") or []]
    max_alias_width = max((width + 2 for values in alias_compacts.values() for _alias, width in values), default=1)
    windows = document_compact_windows(tokens, max_alias_width)
    for label, seed in metadata.items():
        if not seed_possible_in_document(windows, alias_compacts.get(label, ())):
            continue
        for hit in pattern_spans(row, seed, label):
            hit_start = int(hit["token_start"])
            hit_stop = int(hit["token_stop"])
            char_start = int(hit.get("start", 0))
            char_stop = int(hit.get("stop", 0))
            gold, outcome, delta = closest_gold_match(row, hit)
            gold_start = ""
            gold_stop = ""
            gold_surface = ""
            gold_label = ""
            if gold is not None:
                gold_label = str(gold.get("label") or "")
                gold_start, gold_stop = token_span(gold) or ("", "")
                if "surface" in gold:
                    gold_surface = str(gold.get("surface") or "")
                elif isinstance(gold_start, int) and isinstance(gold_stop, int):
                    gold_surface = " ".join(str(token) for token in (row.get("tokens") or [])[gold_start:gold_stop])
            left, right = context(text, char_start, char_stop, context_chars)
            rows.append(
                {
                    "split": split,
                    "document_id": doc_id,
                    "language": row.get("language", ""),
                    "date": row.get("date", ""),
                    "newspaper": row.get("newspaper", ""),
                    "alias": hit.get("alias", ""),
                    "matcher": hit.get("matcher", ""),
                    "predicted_label": label,
                    "hit_token_start": hit_start,
                    "hit_token_stop": hit_stop,
                    "hit_surface": hit.get("surface", ""),
                    "gold_label": gold_label,
                    "gold_token_start": gold_start,
                    "gold_token_stop": gold_stop,
                    "gold_surface": gold_surface,
                    "outcome": outcome,
                    "boundary_delta": "" if delta is None else delta,
                    "left_context": left,
                    "right_context": right,
                }
            )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_outcome = Counter(str(row["outcome"]) for row in rows)
    by_label = Counter(str(row["predicted_label"]) for row in rows)
    by_alias_outcome = Counter(
        f"{row['predicted_label']} || {row['alias']} || {row['outcome']}" for row in rows
    )
    by_matcher_outcome = Counter(f"{row['matcher']} || {row['outcome']}" for row in rows)
    by_alias: dict[tuple[str, str], Counter[str]] = {}
    for row in rows:
        by_alias.setdefault((str(row["predicted_label"]), str(row["alias"])), Counter())[str(row["outcome"])] += 1
    alias_quality = []
    for (label, alias), counts in sorted(by_alias.items()):
        hits = sum(counts.values())
        exact = counts.get("exact", 0)
        lenient = exact + counts.get("same_label_overlap", 0)
        alias_quality.append(
            {
                "label": label,
                "alias": alias,
                "hits": hits,
                "exact": exact,
                "same_label_overlap": counts.get("same_label_overlap", 0),
                "label_conflict": counts.get("label_conflict", 0),
                "false_positive": counts.get("false_positive", 0),
                "precision_exact": round(exact / hits, 4) if hits else 0.0,
                "precision_lenient": round(lenient / hits, 4) if hits else 0.0,
            }
        )
    return {
        "hits": len(rows),
        "by_outcome": dict(sorted(by_outcome.items())),
        "by_label": dict(sorted(by_label.items())),
        "by_alias_outcome": dict(sorted(by_alias_outcome.items())),
        "by_matcher_outcome": dict(sorted(by_matcher_outcome.items())),
        "alias_quality": alias_quality,
    }


def md_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(column, "")).replace("|", "\\|") for column in columns) + " |")
    return out


def write_markdown(path: Path, summary: dict[str, Any], detail_rows: list[dict[str, Any]], *, example_limit: int) -> None:
    alias_quality = sorted(
        summary["alias_quality"],
        key=lambda row: (float(row["precision_lenient"]), -int(row["hits"]), str(row["label"]), str(row["alias"])),
    )
    lines = [
        "# Seed Alias Match Audit",
        "",
        "This read-only report applies seed alias matchers to the current annotated JSONL data and compares each hit with gold entities.",
        "",
        "Outcomes: `exact` = same label and boundaries; `same_label_overlap` = same label but different boundary; `label_conflict` = overlapping gold entity with another label; `false_positive` = no overlapping gold entity.",
        "",
        "## Summary",
        "",
        f"- Hits: {summary['hits']}",
    ]
    for outcome, count in summary["by_outcome"].items():
        lines.append(f"- {outcome}: {count}")
    lines.extend(["", "## Alias Quality", ""])
    lines.extend(
        md_table(
            alias_quality,
            ["label", "alias", "hits", "exact", "same_label_overlap", "label_conflict", "false_positive", "precision_exact", "precision_lenient"],
        )
    )
    for outcome in ["false_positive", "label_conflict", "same_label_overlap"]:
        examples = [row for row in detail_rows if row["outcome"] == outcome][:example_limit]
        if not examples:
            continue
        lines.extend(["", f"## {outcome.replace('_', ' ').title()} Examples", ""])
        lines.extend(
            md_table(
                examples,
                ["split", "document_id", "language", "alias", "predicted_label", "hit_surface", "gold_label", "gold_surface", "left_context", "right_context"],
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_audit(
    *,
    split_inputs: list[tuple[str, Path]],
    metadata_paths: list[Path],
    context_chars: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metadata = load_label_metadata(metadata_paths)
    alias_compacts = {label: seed_match_compacts(seed, label) for label, seed in metadata.items()}
    detail_rows: list[dict[str, Any]] = []
    split_rows = {}
    for split, path in split_inputs:
        rows = load_jsonl(path)
        split_rows[split] = len(rows)
        for row in rows:
            detail_rows.extend(audit_row(split, row, metadata, alias_compacts, context_chars=context_chars))
    detail_rows.sort(
        key=lambda row: (
            str(row["split"]),
            str(row["predicted_label"]),
            str(row["alias"]),
            str(row["document_id"]),
            int(row["hit_token_start"]),
            int(row["hit_token_stop"]),
        )
    )
    summary = summarize(detail_rows)
    summary["splits"] = split_rows
    summary["label_metadata"] = [str(path) for path in metadata_paths]
    return detail_rows, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit seed alias matcher hits against annotated JSONL data.")
    parser.add_argument("--split", action="append", type=parse_split, required=True, help="Split input as NAME=PATH. Can be repeated.")
    parser.add_argument("--label-metadata", action="append", type=Path, default=[])
    parser.add_argument("--details-tsv", required=True, type=Path)
    parser.add_argument("--summary-json", required=True, type=Path)
    parser.add_argument("--report-md", required=True, type=Path)
    parser.add_argument("--context-chars", type=int, default=80)
    parser.add_argument("--example-limit", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    detail_rows, summary = build_audit(
        split_inputs=args.split,
        metadata_paths=args.label_metadata or [Path("resources/newsagency_seeds.json"), Path("resources/radiostation_seeds.json")],
        context_chars=args.context_chars,
    )
    write_tsv(args.details_tsv, detail_rows, TSV_COLUMNS)
    write_json(args.summary_json, summary)
    write_markdown(args.report_md, summary, detail_rows, example_limit=args.example_limit)
    print(json.dumps({"hits": summary["hits"], "by_outcome": summary["by_outcome"], "splits": summary["splits"]}, ensure_ascii=False, sort_keys=True))
    print(f"Details: {args.details_tsv}")
    print(f"Report:  {args.report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
