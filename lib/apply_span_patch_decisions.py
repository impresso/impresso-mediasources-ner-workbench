from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from lib.span_patch_review import load_jsonl, load_span_patches, latest_decisions, write_json


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def tsv_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_tsv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(tsv_cell(row.get(column, "")) for column in columns) + "\n")


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("document_id") or row.get("id") or "")


def entity_family(label: str) -> str:
    if ".pressagency." in label:
        return "pressagency"
    if ".radiostation." in label:
        return "radiostation"
    if ".newspaper." in label:
        return "newspaper"
    return label.rsplit(".", 2)[-2] if "." in label else ""


def token_span_for_offsets(row: dict[str, Any], start: int, stop: int) -> tuple[int, int]:
    starts = [int(value) for value in row.get("token_start_offsets", [])]
    stops = [int(value) for value in row.get("token_end_offsets", [])]
    token_start = next((index for index, value in enumerate(starts) if value == start), None)
    token_stop = next((index + 1 for index, value in enumerate(stops) if value == stop), None)
    if token_start is None or token_stop is None or token_start >= token_stop:
        raise ValueError(f"{row_id(row)}: patch offsets {start}:{stop} do not align with token boundaries")
    return token_start, token_stop


def char_offsets_for_token_span(row: dict[str, Any], token_start: int, token_stop: int) -> tuple[int, int]:
    starts = [int(value) for value in row.get("token_start_offsets", [])]
    stops = [int(value) for value in row.get("token_end_offsets", [])]
    if token_start < 0 or token_stop <= token_start or token_stop > len(starts):
        raise ValueError(f"{row_id(row)}: patch token span {token_start}:{token_stop} is out of range")
    return starts[token_start], stops[token_stop - 1]


def overlaps(a_start: int, a_stop: int, b_start: int, b_stop: int) -> bool:
    return a_start < b_stop and b_start < a_stop


def accepted_patch(decision: dict[str, Any]) -> bool:
    verified = decision.get("audit_status") == "verified" or decision.get("status") == "done"
    return verified and decision.get("choice") in {"accept", "modify", "correct"}


def existing_boundary_patch(patch: dict[str, Any]) -> bool:
    return patch.get("audit_mode") == "existing-span-boundary"


def removal_patch(patch: dict[str, Any]) -> bool:
    return patch.get("audit_mode") == "manual-tsv-remove"


def manual_tsv_patch(patch: dict[str, Any]) -> bool:
    return str(patch.get("audit_mode") or "").startswith("manual-tsv-")


def verified_decision(decision: dict[str, Any]) -> bool:
    return decision.get("audit_status") == "verified" or decision.get("status") == "done"


def decision_source_key(decision: dict[str, Any]) -> tuple[str, str, int, int] | None:
    source = decision.get("source") if isinstance(decision.get("source"), dict) else {}
    if source.get("start") is None or source.get("stop") is None:
        return None
    return (
        str(decision.get("audit_id") or ""),
        str(decision.get("document_id") or ""),
        int(source["start"]),
        int(source["stop"]),
    )


def latest_decision_per_source_span(decisions: dict[str, dict[str, Any]], patches: dict[str, dict[str, Any]]) -> set[str]:
    latest: dict[tuple[str, str, int, int], tuple[str, int, str]] = {}
    keep_ids: set[str] = set()
    for order, (review_id, decision) in enumerate(decisions.items()):
        patch = patches.get(review_id)
        if not patch or not manual_tsv_patch(patch):
            keep_ids.add(review_id)
            continue
        key = decision_source_key(decision)
        if key is None:
            keep_ids.add(review_id)
            continue
        reviewed_at = str(decision.get("reviewed_at") or "")
        current = latest.get(key)
        if current is None or (reviewed_at, order, review_id) > current:
            latest[key] = (reviewed_at, order, review_id)
    keep_ids.update(review_id for _reviewed_at, _order, review_id in latest.values())
    return keep_ids


def decision_apply_order(decisions: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        decisions.items(),
        key=lambda item: (str(item[1].get("reviewed_at") or ""), str(item[0])),
    )


def audit_mark(decision: dict[str, Any]) -> dict[str, Any]:
    source = decision.get("source") if isinstance(decision.get("source"), dict) else {}
    span = decision.get("span") if isinstance(decision.get("span"), dict) else {}
    source_label = source.get("label") or decision.get("correct_label", "")
    source_start = int(source.get("start"))
    source_stop = int(source.get("stop"))
    if source_label == "O" and isinstance(span, dict) and decision.get("choice") in {"accept", "modify", "correct"}:
        source_label = span.get("label") or source_label
        source_start = int(span.get("start", source_start))
        source_stop = int(span.get("stop", source_stop))
    mark = {
        "audit_id": decision.get("audit_id", ""),
        "decision": decision.get("choice", ""),
        "label": source_label,
        "start": source_start,
        "status": "verified",
        "stop": source_stop,
    }
    if decision.get("choice") in {"modify", "correct"}:
        mark["applied_label"] = span.get("label") or decision.get("correct_label", "")
        mark["applied_start"] = int(span.get("start"))
        mark["applied_stop"] = int(span.get("stop"))
    return mark


def add_audit_mark(row: dict[str, Any], mark: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    marks = [dict(item) for item in out.get("audit_marks", []) if isinstance(item, dict)]
    key = (mark.get("audit_id"), mark.get("label"), mark.get("start"), mark.get("stop"), mark.get("decision"))
    existing_keys = {
        (item.get("audit_id"), item.get("label"), item.get("start"), item.get("stop"), item.get("decision"))
        for item in marks
    }
    if key not in existing_keys:
        marks.append(mark)
    out["audit_marks"] = sorted(marks, key=lambda item: (str(item.get("audit_id", "")), int(item.get("start", 0)), int(item.get("stop", 0)), str(item.get("label", ""))))
    return out


def audit_mark_keys(row: dict[str, Any]) -> set[tuple[Any, Any, Any, Any, Any]]:
    return {
        (item.get("audit_id"), item.get("label"), item.get("start"), item.get("stop"), item.get("decision"))
        for item in row.get("audit_marks", [])
        if isinstance(item, dict)
    }


def patch_span(row: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    span = decision.get("span") if isinstance(decision.get("span"), dict) else {}
    label = str(span.get("label") or decision.get("correct_label") or "")
    if span.get("token_start") is not None and span.get("token_stop") is not None:
        token_start = int(span["token_start"])
        token_stop = int(span["token_stop"])
        start, stop = char_offsets_for_token_span(row, token_start, token_stop)
        return {
            "label": label,
            "start": start,
            "stop": stop,
            "token_start": token_start,
            "token_stop": token_stop,
        }
    return {
        "label": label,
        "start": int(span["start"]),
        "stop": int(span["stop"]),
    }


def add_or_replace_entity(row: dict[str, Any], decision: dict[str, Any], *, replace_overlaps: bool) -> tuple[dict[str, Any], dict[str, Any] | None]:
    span = patch_span(row, decision)
    if span.get("token_start") is not None and span.get("token_stop") is not None:
        token_start = int(span["token_start"])
        token_stop = int(span["token_stop"])
    else:
        try:
            token_start, token_stop = token_span_for_offsets(row, span["start"], span["stop"])
        except ValueError as exc:
            raise ValueError(
                f"{decision.get('review_id', '<unknown>')}: {exc}. "
                "Re-review this item with token-based manual span syntax; old character-based decisions cannot be applied."
            ) from exc
    text = str(row.get("text") or "")
    surface = text[span["start"] : span["stop"]]
    existing = list(row.get("entities") or [])
    conflicts = [
        entity
        for entity in existing
        if overlaps(int(entity["start"]), int(entity["stop"]), span["start"], span["stop"])
        and not (int(entity["start"]) == span["start"] and int(entity["stop"]) == span["stop"] and entity.get("label") == span["label"])
    ]
    if conflicts and not replace_overlaps:
        labels = ", ".join(str(entity.get("label", "")) for entity in conflicts)
        raise ValueError(f"{row_id(row)}: patch overlaps existing entity labels: {labels}")
    if replace_overlaps:
        existing = [
            entity
            for entity in existing
            if not overlaps(int(entity["start"]), int(entity["stop"]), span["start"], span["stop"])
            or (int(entity["start"]) == span["start"] and int(entity["stop"]) == span["stop"] and entity.get("label") == span["label"])
        ]
    exists = any(
        int(entity["start"]) == span["start"] and int(entity["stop"]) == span["stop"] and entity.get("label") == span["label"]
        for entity in existing
    )
    if not exists:
        existing.append(
            {
                "entity_family": entity_family(span["label"]),
                "label": span["label"],
                "start": span["start"],
                "stop": span["stop"],
                "surface": surface,
                "token_start": token_start,
                "token_stop": token_stop,
            }
        )
    out = dict(row)
    out["entities"] = sorted(existing, key=lambda entity: (int(entity["start"]), int(entity["stop"]), str(entity["label"])))
    out["token_labels"] = labels_from_entities(out)
    if exists:
        return out, None
    return out, {
        "choice": decision.get("choice"),
        "document_id": row_id(row),
        "label": span["label"],
        "review_id": decision["review_id"],
        "start": span["start"],
        "stop": span["stop"],
        "surface": surface,
        "token_start": token_start,
        "token_stop": token_stop,
    }


def remove_source_entity(row: dict[str, Any], decision: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = decision.get("source") if isinstance(decision.get("source"), dict) else {}
    start = int(source["start"])
    stop = int(source["stop"])
    label = str(source["label"])
    existing = list(row.get("entities") or [])
    kept = [
        entity
        for entity in existing
        if not (int(entity["start"]) == start and int(entity["stop"]) == stop and str(entity.get("label") or "") == label)
    ]
    if len(kept) == len(existing):
        raise ValueError(f"{row_id(row)}: source entity not found for removal: {start}:{stop} {label}")
    out = dict(row)
    out["entities"] = sorted(kept, key=lambda entity: (int(entity["start"]), int(entity["stop"]), str(entity["label"])))
    out["token_labels"] = labels_from_entities(out)
    return out, {
        "choice": decision.get("choice"),
        "document_id": row_id(row),
        "label": label,
        "review_id": decision["review_id"],
        "start": start,
        "stop": stop,
        "surface": source.get("surface", ""),
        "token_start": source.get("token_start"),
        "token_stop": source.get("token_stop"),
    }


def remove_overlapping_entities(row: dict[str, Any], decision: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    span = patch_span(row, decision)
    existing = list(row.get("entities") or [])
    removed = [
        entity
        for entity in existing
        if overlaps(int(entity["start"]), int(entity["stop"]), span["start"], span["stop"])
    ]
    kept = [
        entity
        for entity in existing
        if not overlaps(int(entity["start"]), int(entity["stop"]), span["start"], span["stop"])
    ]
    if not removed:
        return row, None
    out = dict(row)
    out["entities"] = sorted(kept, key=lambda entity: (int(entity["start"]), int(entity["stop"]), str(entity["label"])))
    out["token_labels"] = labels_from_entities(out)
    labels = sorted({str(entity.get("label") or "") for entity in removed})
    text = str(row.get("text") or "")
    return out, {
        "choice": decision.get("choice"),
        "document_id": row_id(row),
        "label": "O",
        "removed_labels": ",".join(labels),
        "review_id": decision["review_id"],
        "start": span["start"],
        "stop": span["stop"],
        "surface": text[span["start"] : span["stop"]],
        "token_start": span.get("token_start"),
        "token_stop": span.get("token_stop"),
    }


def labels_from_entities(row: dict[str, Any]) -> list[str]:
    labels = ["O"] * len(row.get("tokens", []))
    for entity in row.get("entities") or []:
        token_start = int(entity["token_start"])
        token_stop = int(entity["token_stop"])
        label = str(entity["label"])
        for index in range(token_start, token_stop):
            if labels[index] != "O":
                raise ValueError(f"{row_id(row)}: overlapping token label at token {index}")
            labels[index] = f"{'B' if index == token_start else 'I'}-{label}"
    return labels


def apply_span_patches(
    *,
    input_jsonl: Path,
    output_jsonl: Path,
    candidates_path: Path,
    decisions_path: Path,
    audit_id: str,
    changes_jsonl: Path,
    changes_tsv: Path,
    summary_json: Path,
    target_label: str = "",
    replace_overlaps: bool = False,
) -> dict[str, Any]:
    rows = load_jsonl(input_jsonl)
    rows_by_id = {row_id(row): row for row in rows}
    patches = {patch["review_id"]: patch for patch in load_span_patches(candidates_path, audit_id=audit_id, target_label=target_label)}
    decisions = latest_decisions(decisions_path)
    active_decision_ids = latest_decision_per_source_span(decisions, patches)
    changes: list[dict[str, Any]] = []
    changed_ids: set[str] = set()
    audit_marks_written = 0

    for review_id, decision in decision_apply_order(decisions):
        if review_id not in active_decision_ids or review_id not in patches or not verified_decision(decision):
            continue
        doc_id = str(decision["document_id"])
        if doc_id not in rows_by_id:
            raise ValueError(f"{review_id}: source document not found: {doc_id}")
        patch = patches[review_id]
        before_audit_marks = audit_mark_keys(rows_by_id[doc_id])
        rows_by_id[doc_id] = add_audit_mark(rows_by_id[doc_id], audit_mark(decision))
        if audit_mark_keys(rows_by_id[doc_id]) != before_audit_marks:
            audit_marks_written += 1
        if existing_boundary_patch(patch) and decision.get("choice") == "accept":
            continue
        if existing_boundary_patch(patch) and decision.get("choice") == "reject":
            rows_by_id[doc_id], change = remove_source_entity(rows_by_id[doc_id], decision)
            change.update(
                {
                    "audit_id": audit_id,
                    "date": rows_by_id[doc_id].get("date", ""),
                    "language": rows_by_id[doc_id].get("language", ""),
                    "newspaper": rows_by_id[doc_id].get("newspaper", ""),
                    "suggested_label": patch.get("suggested_label", ""),
                    "target_label": patch.get("target_label", ""),
                }
            )
            changes.append(change)
            changed_ids.add(doc_id)
            continue
        if removal_patch(patch) and accepted_patch(decision):
            rows_by_id[doc_id], change = remove_overlapping_entities(rows_by_id[doc_id], decision)
            if change is not None:
                change.update(
                    {
                        "audit_id": audit_id,
                        "date": rows_by_id[doc_id].get("date", ""),
                        "language": rows_by_id[doc_id].get("language", ""),
                        "newspaper": rows_by_id[doc_id].get("newspaper", ""),
                        "suggested_label": patch.get("suggested_label", ""),
                        "target_label": patch.get("target_label", ""),
                    }
                )
                changes.append(change)
                changed_ids.add(doc_id)
            continue
        if not accepted_patch(decision):
            continue
        rows_by_id[doc_id], change = add_or_replace_entity(
            rows_by_id[doc_id],
            decision,
            replace_overlaps=replace_overlaps or existing_boundary_patch(patch) or manual_tsv_patch(patch),
        )
        if change is not None:
            change.update(
                {
                    "audit_id": audit_id,
                    "date": rows_by_id[doc_id].get("date", ""),
                    "language": rows_by_id[doc_id].get("language", ""),
                    "newspaper": rows_by_id[doc_id].get("newspaper", ""),
                    "suggested_label": patch.get("suggested_label", ""),
                    "target_label": patch.get("target_label", ""),
                }
            )
            changes.append(change)
            changed_ids.add(doc_id)

    output_rows = [rows_by_id[row_id(row)] for row in rows]
    write_jsonl(output_jsonl, output_rows)
    write_jsonl(changes_jsonl, changes)
    write_tsv(
        changes_tsv,
        changes,
        ["review_id", "document_id", "language", "date", "newspaper", "choice", "label", "removed_labels", "surface", "start", "stop", "token_start", "token_stop"],
    )
    summary = {
        "audit_id": audit_id,
        "input_jsonl": str(input_jsonl),
        "output_jsonl": str(output_jsonl),
        "candidate_patches": len(patches),
        "decisions": len(decisions),
        "audit_marks_written": audit_marks_written,
        "applied": len(changes),
        "documents_changed": len(changed_ids),
        "changes_jsonl": str(changes_jsonl),
        "changes_tsv": str(changes_tsv),
    }
    write_json(summary_json, summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply reviewed generic audit span patch decisions to one JSONL split.")
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--changes-jsonl", required=True)
    parser.add_argument("--changes-tsv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--target-label", default="")
    parser.add_argument("--replace-overlaps", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = apply_span_patches(
        input_jsonl=Path(args.input_jsonl),
        output_jsonl=Path(args.output_jsonl),
        candidates_path=Path(args.candidates),
        decisions_path=Path(args.decisions),
        audit_id=args.audit_id,
        changes_jsonl=Path(args.changes_jsonl),
        changes_tsv=Path(args.changes_tsv),
        summary_json=Path(args.summary_json),
        target_label=args.target_label,
        replace_overlaps=args.replace_overlaps,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    print(f"accepted TSV decisions applied: {summary['applied']} change(s) in {summary['documents_changed']} document(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
