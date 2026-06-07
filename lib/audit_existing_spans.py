from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def tsv_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = ["document_id", "language", "date", "newspaper", "label", "surface", "start", "stop", "token_start", "token_stop"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(tsv_cell(row.get(column, "")) for column in columns) + "\n")


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("document_id") or row.get("id") or "")


def entity_surface(row: dict[str, Any], entity: dict[str, Any]) -> str:
    if entity.get("surface"):
        return str(entity["surface"])
    text = str(row.get("text") or "")
    start = int(entity["start"])
    stop = int(entity["stop"])
    return text[start:stop]


def entity_key(entity: dict[str, Any]) -> tuple[int, int, str]:
    return int(entity["start"]), int(entity["stop"]), str(entity["label"])


def has_verified_audit_mark(row: dict[str, Any], *, audit_id: str, entity: dict[str, Any]) -> bool:
    start, stop, label = entity_key(entity)
    marks = row.get("audit_marks")
    if not isinstance(marks, list):
        return False
    for mark in marks:
        if not isinstance(mark, dict):
            continue
        if mark.get("audit_id") != audit_id or mark.get("status") != "verified":
            continue
        if int(mark.get("start", -1)) == start and int(mark.get("stop", -1)) == stop and str(mark.get("label") or "") == label:
            return True
    return False


def build_candidates(input_jsonl: Path, *, target_label: str, audit_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not target_label:
        raise ValueError("target_label is required")
    rows = load_jsonl(input_jsonl)
    candidates: list[dict[str, Any]] = []
    tsv_rows: list[dict[str, Any]] = []
    by_language: dict[str, int] = {}

    for row in rows:
        spans = []
        for entity in row.get("entities") or []:
            if not isinstance(entity, dict) or entity.get("label") != target_label:
                continue
            if has_verified_audit_mark(row, audit_id=audit_id, entity=entity):
                continue
            span = {
                "label": target_label,
                "start": int(entity["start"]),
                "stop": int(entity["stop"]),
                "surface": entity_surface(row, entity),
                "token_start": entity.get("token_start"),
                "token_stop": entity.get("token_stop"),
            }
            spans.append(span)
            language = str(row.get("language") or "")
            by_language[language] = by_language.get(language, 0) + 1
            tsv_rows.append(
                {
                    "date": row.get("date", ""),
                    "document_id": row_id(row),
                    "label": target_label,
                    "language": language,
                    "newspaper": row.get("newspaper", ""),
                    "start": span["start"],
                    "stop": span["stop"],
                    "surface": span["surface"],
                    "token_start": span.get("token_start"),
                    "token_stop": span.get("token_stop"),
                }
            )
        if not spans:
            continue
        candidates.append(
            {
                "audit_mode": "existing-span-boundary",
                "date": row.get("date", ""),
                "document_id": row_id(row),
                "language": row.get("language", ""),
                "newspaper": row.get("newspaper", ""),
                "candidate_spans": sorted(spans, key=entity_key),
                "target_label": target_label,
                "text": row.get("text", ""),
                "token_end_offsets": row.get("token_end_offsets", []),
                "token_start_offsets": row.get("token_start_offsets", []),
                "tokens": row.get("tokens", []),
            }
        )

    candidates.sort(key=lambda row: str(row["document_id"]))
    tsv_rows.sort(key=lambda row: (str(row["document_id"]), int(row["start"]), int(row["stop"])))
    summary = {
        "audit_id": audit_id,
        "audit_mode": "existing-span-boundary",
        "input_jsonl": str(input_jsonl),
        "target_label": target_label,
        "documents": len(rows),
        "candidate_documents": len(candidates),
        "candidate_spans": len(tsv_rows),
        "candidate_spans_by_language": dict(sorted(by_language.items())),
    }
    return candidates, tsv_rows, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an audit queue for boundary review of existing annotated spans.")
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--target-label", required=True)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--candidates-jsonl", required=True)
    parser.add_argument("--candidates-tsv", required=True)
    parser.add_argument("--summary-json", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates, tsv_rows, summary = build_candidates(Path(args.input_jsonl), target_label=args.target_label, audit_id=args.audit_id)
    write_jsonl(Path(args.candidates_jsonl), candidates)
    write_tsv(Path(args.candidates_tsv), tsv_rows)
    write_json(Path(args.summary_json), summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
