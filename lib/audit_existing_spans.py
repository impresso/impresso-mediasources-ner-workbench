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


def build_candidates(input_jsonl: Path, *, target_label: str, audit_id: str, limit: int = 0) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not target_label:
        raise ValueError("target_label is required")
    if limit < 0:
        raise ValueError("limit must be non-negative")
    rows = load_jsonl(input_jsonl)
    candidate_rows_by_document: dict[str, dict[str, Any]] = {}
    span_records: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    total_by_language: dict[str, int] = {}

    for row in rows:
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
            language = str(row.get("language") or "")
            total_by_language[language] = total_by_language.get(language, 0) + 1
            span_records.append(
                (
                    row,
                    span,
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
                    },
                )
            )

    span_records.sort(key=lambda item: (row_id(item[0]), int(item[1]["start"]), int(item[1]["stop"])))
    total_candidate_spans = len(span_records)
    selected_span_records = span_records[:limit] if limit else span_records
    tsv_rows = [tsv_row for _row, _span, tsv_row in selected_span_records]
    queued_by_language: dict[str, int] = {}
    for row, _span, _tsv_row in selected_span_records:
        language = str(row.get("language") or "")
        queued_by_language[language] = queued_by_language.get(language, 0) + 1

    for row, span, _tsv_row in selected_span_records:
        document_id = row_id(row)
        candidate = candidate_rows_by_document.get(document_id)
        if candidate is None:
            candidate = {
                "audit_mode": "existing-span-boundary",
                "date": row.get("date", ""),
                "document_id": document_id,
                "language": row.get("language", ""),
                "newspaper": row.get("newspaper", ""),
                "candidate_spans": [],
                "target_label": target_label,
                "text": row.get("text", ""),
                "token_end_offsets": row.get("token_end_offsets", []),
                "token_start_offsets": row.get("token_start_offsets", []),
                "tokens": row.get("tokens", []),
            }
            candidate_rows_by_document[document_id] = candidate
        candidate["candidate_spans"].append(span)

    candidates = list(candidate_rows_by_document.values())
    candidates.sort(key=lambda row: str(row["document_id"]))
    for candidate in candidates:
        candidate["candidate_spans"].sort(key=entity_key)
    tsv_rows.sort(key=lambda row: (str(row["document_id"]), int(row["start"]), int(row["stop"])))
    exhaustive = limit == 0 or total_candidate_spans <= limit
    summary = {
        "audit_id": audit_id,
        "audit_mode": "existing-span-boundary",
        "input_jsonl": str(input_jsonl),
        "target_label": target_label,
        "limit": limit,
        "exhaustive": exhaustive,
        "documents": len(rows),
        "candidate_documents": len(candidates),
        "candidate_spans": len(tsv_rows),
        "total_candidate_spans": total_candidate_spans,
        "omitted_candidate_spans": max(0, total_candidate_spans - len(tsv_rows)),
        "candidate_spans_by_language": dict(sorted(queued_by_language.items())),
        "total_candidate_spans_by_language": dict(sorted(total_by_language.items())),
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
    parser.add_argument("--limit", type=int, default=0, help="Maximum existing spans to queue; 0 means exhaustive.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates, tsv_rows, summary = build_candidates(Path(args.input_jsonl), target_label=args.target_label, audit_id=args.audit_id, limit=args.limit)
    write_jsonl(Path(args.candidates_jsonl), candidates)
    write_tsv(Path(args.candidates_tsv), tsv_rows)
    write_json(Path(args.summary_json), summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if not summary["exhaustive"]:
        print(
            "audit queue is not exhaustive: "
            f"queued {summary['candidate_spans']} of {summary['total_candidate_spans']} eligible spans; "
            "rerun with --limit 0 for a complete audit"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
