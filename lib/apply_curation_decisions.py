from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from lib.build_curation_review import natural_text
from lib.import_legacy_hipe_tsv import make_label_map


CORRECTION_RE = re.compile(
    r'(?P<start>\d+):(?P<stop>\d+)\s+"(?P<surface>[^"]+)"\s+label=(?P<label>[A-Za-z0-9_.-]+)'
)


@dataclass(frozen=True)
class Span:
    token_start: int
    token_stop: int
    label: str

    def overlaps(self, other: "Span") -> bool:
        return self.token_start < other.token_stop and other.token_start < self.token_stop


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row["_line_number"] = line_number
            rows.append(row)
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def latest_decisions(path: Path) -> dict[str, dict[str, Any]]:
    decisions = {}
    for row in load_jsonl(path):
        review_id = row.get("review_id")
        if review_id:
            decisions[review_id] = row
    return decisions


def span_from_entity(entity: dict[str, Any] | None) -> Span | None:
    if not entity:
        return None
    return Span(int(entity["token_start"]), int(entity["token_stop"]), str(entity["label"]))


def parse_correction(notes: str) -> Span | None:
    match = CORRECTION_RE.search(notes or "")
    if not match:
        return None
    start = int(match.group("start"))
    stop = int(match.group("stop"))
    if start >= stop:
        raise ValueError(f"invalid correction span {start}:{stop}")
    return Span(start, stop, match.group("label"))


def spans_from_decision(decision: dict[str, Any]) -> list[Span]:
    spans = []
    raw_spans = decision.get("accepted_spans")
    if not isinstance(raw_spans, list):
        return spans
    for raw_span in raw_spans:
        if not isinstance(raw_span, dict):
            continue
        start = int(raw_span["token_start"])
        stop = int(raw_span["token_stop"])
        if start >= stop:
            raise ValueError(f"invalid manual span {start}:{stop}")
        spans.append(Span(start, stop, str(raw_span["label"])))
    return spans


def entity_to_span(entity: dict[str, Any]) -> Span:
    return Span(int(entity["token_start"]), int(entity["token_stop"]), str(entity["label"]))


def spans_from_row(row: dict[str, Any]) -> list[Span]:
    return [entity_to_span(entity) for entity in row.get("entities", [])]


def remove_overlapping(spans: list[Span], targets: Iterable[Span | None]) -> list[Span]:
    target_spans = [target for target in targets if target is not None]
    if not target_spans:
        return spans
    return [span for span in spans if not any(span.overlaps(target) for target in target_spans)]


def add_span(spans: list[Span], span: Span) -> list[Span]:
    for existing in spans:
        if existing.overlaps(span) and existing != span:
            raise ValueError(f"overlapping spans are not supported: {existing} vs {span}")
    if span not in spans:
        spans.append(span)
    return spans


def apply_decision(spans: list[Span], item: dict[str, Any], decision: dict[str, Any]) -> tuple[list[Span], dict[str, Any]]:
    gold = span_from_entity(item.get("gold"))
    prediction = span_from_entity(item.get("prediction"))
    manual_spans = spans_from_decision(decision)
    correction = manual_spans[0] if len(manual_spans) == 1 else parse_correction(str(decision.get("notes", "")))
    choice = decision.get("choice")
    before = sorted(spans, key=lambda span: (span.token_start, span.token_stop, span.label))
    action = "unchanged"

    if choice == "gold":
        if correction:
            spans = remove_overlapping(spans, [gold, prediction, correction])
            spans = add_span(spans, correction)
            action = "replaced_with_correction"
        elif gold is None:
            spans = remove_overlapping(spans, [prediction])
            action = "accepted_empty_gold"
        else:
            action = "kept_gold"
    elif choice == "prediction":
        target = correction or prediction
        if target is None:
            spans = remove_overlapping(spans, [gold])
            action = "accepted_empty_prediction"
        else:
            spans = remove_overlapping(spans, [gold, prediction, target])
            spans = add_span(spans, target)
            action = "accepted_prediction" if correction is None else "accepted_prediction_correction"
    elif choice == "neither":
        spans = remove_overlapping(spans, [gold, prediction])
        if correction:
            spans = remove_overlapping(spans, [correction])
            spans = add_span(spans, correction)
            action = "replaced_with_correction"
        else:
            action = "removed_displayed_spans"
    elif choice == "both":
        targets = [span for span in [gold, prediction, correction] if span is not None]
        if not targets:
            raise ValueError(f"{item['review_id']}: choice=both but no spans are available")
        spans = remove_overlapping(spans, [prediction, correction])
        for target in targets:
            spans = add_span(spans, target)
        action = "kept_both"
    elif choice == "manual":
        if not manual_spans:
            raise ValueError(f"{item['review_id']}: choice=manual but accepted_spans is empty")
        spans = remove_overlapping(spans, [gold, prediction, *manual_spans])
        for manual_span in manual_spans:
            spans = add_span(spans, manual_span)
        action = "manual_correction"
    elif choice == "skip":
        action = "ignored"
    else:
        raise ValueError(f"{item['review_id']}: unsupported choice {choice!r}")

    after = sorted(spans, key=lambda span: (span.token_start, span.token_stop, span.label))
    return spans, {
        "review_id": item["review_id"],
        "document_id": item["document"]["id"],
        "split": item["split"],
        "choice": choice,
        "action": action,
        "focus": {
            "gold": gold.__dict__ if gold else None,
            "prediction": prediction.__dict__ if prediction else None,
            "correction": correction.__dict__ if correction else None,
            "manual_spans": [span.__dict__ for span in manual_spans],
        },
        "before": [span.__dict__ for span in before],
        "after": [span.__dict__ for span in after],
        "notes": decision.get("notes", ""),
        "reviewer": decision.get("reviewer", ""),
        "reviewed_at": decision.get("reviewed_at", ""),
    }


def rebuild_row(row: dict[str, Any], spans: list[Span]) -> dict[str, Any]:
    out = {key: value for key, value in row.items() if key != "_line_number"}
    original_entities = {entity_to_span(entity): entity for entity in row.get("entities", [])}
    token_count = len(out["tokens"])
    labels = ["O"] * token_count
    entities = []
    for entity_index, span in enumerate(sorted(spans, key=lambda item: (item.token_start, item.token_stop, item.label))):
        if span.token_start < 0 or span.token_stop > token_count or span.token_start >= span.token_stop:
            raise ValueError(f"{out['id']}: invalid span {span}")
        for index in range(span.token_start, span.token_stop):
            if labels[index] != "O":
                raise ValueError(f"{out['id']}: overlapping BIO label at token {index}")
            prefix = "B" if index == span.token_start else "I"
            labels[index] = f"{prefix}-{span.label}"
        start = out["token_start_offsets"][span.token_start]
        stop = out["token_end_offsets"][span.token_stop - 1]
        surface = out["text"][start:stop]
        entity = dict(original_entities.get(span, {}))
        entity.update(
            {
                "entity_id": f"{out['id']}#ent-{entity_index}",
                "token_start": span.token_start,
                "token_stop": span.token_stop,
                "start": start,
                "stop": stop,
                "surface": surface,
                "label": span.label,
                "entity_family": entity_family(span.label),
                "status": "accepted",
            }
        )
        entity.setdefault("normalized_surface", surface)
        entity.setdefault("label_original", span.label)
        entity.setdefault("nel", "")
        entity.setdefault("wikidata_url", None)
        entity.setdefault("has_ocr_correction", False)
        entity.setdefault("max_ocr_levenshtein", 0.0)
        entities.append(entity)
    out["token_labels"] = labels
    out["entities"] = entities
    return out


def validate_output_row(row: dict[str, Any], label_map: dict[str, Any]) -> None:
    token_count = len(row["tokens"])
    for field_name in ["token_start_offsets", "token_end_offsets", "token_labels"]:
        if len(row[field_name]) != token_count:
            raise ValueError(f"{row['id']}: {field_name} length does not match tokens")
    if "token_label_ids" in row and len(row["token_label_ids"]) != token_count:
        raise ValueError(f"{row['id']}: token_label_ids length does not match tokens")
    for token, start, stop in zip(row["tokens"], row["token_start_offsets"], row["token_end_offsets"], strict=True):
        if row["text"][start:stop] != token:
            raise ValueError(f"{row['id']}: token offset mismatch for {token!r}")
    label2id = label_map["label2id"]
    for index, label in enumerate(row["token_labels"]):
        if label not in label2id:
            raise ValueError(f"{row['id']}: token label missing from label map: {label}")
        if "token_label_ids" in row and row["token_label_ids"][index] != label2id[label]:
            raise ValueError(f"{row['id']}: token_label_ids mismatch")
        validate_allowed_label(row["id"], label)
    for entity in row["entities"]:
        if row["text"][entity["start"] : entity["stop"]] != entity["surface"]:
            raise ValueError(f"{row['id']}: entity surface mismatch")
        validate_allowed_label(row["id"], str(entity["label"]))


def validate_allowed_label(row_id: str, label: str) -> None:
    lowered = label.lower()
    base = lowered[2:] if lowered.startswith(("b-", "i-")) else lowered
    if base in {"org.ent.pressagency.unk", "org.ent.pressagency.ag", "pers.ind.articleauthor"}:
        raise ValueError(f"{row_id}: forbidden public label {label}")


def entity_family(label: str) -> str:
    if ".radiostation." in label:
        return "radiostation"
    if ".pressagency." in label:
        return "pressagency"
    return ""


def apply_curation(
    *,
    input_dir: Path,
    output_dir: Path,
    disagreements_path: Path,
    decisions_path: Path,
    splits: list[str],
    require_complete: bool,
) -> dict[str, Any]:
    disagreements = load_jsonl(disagreements_path)
    decisions = latest_decisions(decisions_path)
    rows_by_split = {split: load_jsonl(input_dir / f"{split}.jsonl") for split in splits}
    if (input_dir / "train.jsonl").is_file() and "train" not in rows_by_split:
        rows_by_split["train"] = load_jsonl(input_dir / "train.jsonl")
    rows_by_id = {row["id"]: row for rows in rows_by_split.values() for row in rows}
    spans_by_id = {row_id: spans_from_row(row) for row_id, row in rows_by_id.items()}
    audit_rows = []
    missing = []

    for item in disagreements:
        review_id = item["review_id"]
        decision = decisions.get(review_id)
        if decision is None or decision.get("status") == "todo":
            missing.append(review_id)
            continue
        if decision.get("status") not in {"done", "ignored"}:
            raise ValueError(f"{review_id}: unsupported decision status {decision.get('status')!r}")
        doc_id = item["document"]["id"]
        if doc_id not in spans_by_id:
            raise ValueError(f"{review_id}: source document not found: {doc_id}")
        spans, audit = apply_decision(spans_by_id[doc_id], item, decision)
        spans_by_id[doc_id] = spans
        audit_rows.append(audit)

    if require_complete and missing:
        preview = ", ".join(sorted(missing)[:10])
        suffix = " ..." if len(missing) > 10 else ""
        raise ValueError(f"curation incomplete: {len(missing)} review_ids are not done: {preview}{suffix}")

    output_rows_by_split: dict[str, list[dict[str, Any]]] = {}
    all_rows = []
    for split, rows in rows_by_split.items():
        output_rows = [rebuild_row(row, spans_by_id[row["id"]]) for row in rows]
        output_rows_by_split[split] = output_rows
        all_rows.extend(output_rows)

    label_map = make_label_map(all_rows)
    label2id = label_map["label2id"]
    for row in all_rows:
        if "token_label_ids" in row:
            row["token_label_ids"] = [label2id[label] for label in row["token_labels"]]
    for row in all_rows:
        validate_output_row(row, label_map)

    output_dir.mkdir(parents=True, exist_ok=True)
    for split, output_rows in output_rows_by_split.items():
        write_jsonl(output_dir / f"{split}.jsonl", output_rows)
    write_json(output_dir / "label_map.json", label_map)
    write_jsonl(output_dir / "curation_changes.jsonl", audit_rows)
    write_change_tsv(output_dir / "curation_changes_tags.tsv", rows_by_id, {row["id"]: row for row in all_rows}, audit_rows)
    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "decisions": len(decisions),
        "disagreements": len(disagreements),
        "applied": len(audit_rows),
        "missing": len(missing),
        "splits": splits,
    }
    write_json(output_dir / "curation_summary.json", summary)
    return summary


def write_change_tsv(
    path: Path,
    original_rows_by_id: dict[str, dict[str, Any]],
    revised_rows_by_id: dict[str, dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    *,
    radius: int = 8,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for audit in audit_rows:
            doc_id = audit["document_id"]
            original = original_rows_by_id[doc_id]
            revised = revised_rows_by_id[doc_id]
            start, stop = focus_window(audit, len(original["tokens"]), radius=radius)
            handle.write(f"# review_id = {audit['review_id']}\n")
            handle.write(f"# document_id = {doc_id}\n")
            handle.write(f"# split = {audit['split']}\n")
            handle.write(f"# action = {audit['action']}\n")
            if audit.get("notes"):
                handle.write(f"# notes = {audit['notes']}\n")
            handle.write(f"# context = {natural_text(original, start, stop)}\n")
            handle.write("TOKEN\tBEFORE_NERTAG\tAFTER_NERTAG\n")
            for token, before_label, after_label in zip(
                original["tokens"][start:stop],
                original["token_labels"][start:stop],
                revised["token_labels"][start:stop],
                strict=True,
            ):
                handle.write(f"{token}\t{before_label}\t{after_label}\n")
            handle.write("\n")


def focus_window(audit: dict[str, Any], token_count: int, *, radius: int) -> tuple[int, int]:
    spans = []
    for key in ("gold", "prediction", "correction"):
        value = audit.get("focus", {}).get(key)
        if value:
            spans.append((int(value["token_start"]), int(value["token_stop"])))
    for key in ("before", "after"):
        for value in audit.get(key, []):
            spans.append((int(value["token_start"]), int(value["token_stop"])))
    if not spans:
        return 0, min(token_count, radius * 2)
    start = max(0, min(span[0] for span in spans) - radius)
    stop = min(token_count, max(span[1] for span in spans) + radius)
    return start, stop


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply reviewed curation decisions to legacy JSONL annotations.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--disagreements", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--splits", default="train validation test")
    parser.add_argument("--require-complete", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = apply_curation(
            input_dir=Path(args.input_dir),
            output_dir=Path(args.output_dir),
            disagreements_path=Path(args.disagreements),
            decisions_path=Path(args.decisions),
            splits=args.splits.split(),
            require_complete=args.require_complete,
        )
    except Exception as exc:
        print(f"apply curation failed: {exc}")
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
