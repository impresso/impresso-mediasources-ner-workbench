from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def tsv_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_tsv(path: str | Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(tsv_cell(row.get(column, "")) for column in columns) + "\n")


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("document_id") or row.get("id") or "")


def token_label_ids(row: dict[str, Any], label2id: dict[str, int]) -> list[int]:
    ids = row.get("token_label_ids")
    if isinstance(ids, list) and len(ids) == len(row.get("tokens", [])):
        return [int(value) for value in ids]
    labels = row.get("token_labels") or []
    return [int(label2id[label]) for label in labels]


def has_entities(row: dict[str, Any]) -> bool:
    return bool(row.get("entities"))


def prepare_empty_docs(input_jsonl: Path, label_map_path: Path, output_jsonl: Path, summary_json: Path) -> dict[str, Any]:
    label_map = load_json(label_map_path)
    label2id = {str(label): int(idx) for label, idx in label_map["label2id"].items()}
    source_rows = load_jsonl(input_jsonl)
    empty_rows: list[dict[str, Any]] = []
    by_language: dict[str, int] = {}
    for row in source_rows:
        if has_entities(row):
            continue
        out = dict(row)
        out["id"] = row_id(out)
        out["token_label_ids"] = token_label_ids(out, label2id)
        empty_rows.append(out)
        language = str(out.get("language") or "")
        by_language[language] = by_language.get(language, 0) + 1

    empty_rows.sort(key=row_id)
    write_jsonl(output_jsonl, empty_rows)
    summary = {
        "input_jsonl": str(input_jsonl),
        "output_jsonl": str(output_jsonl),
        "total_documents": len(source_rows),
        "empty_documents": len(empty_rows),
        "empty_documents_by_language": dict(sorted(by_language.items())),
    }
    write_json(summary_json, summary)
    return summary


def strip_bio(label: str) -> str:
    if label == "O":
        return "O"
    if label.startswith(("B-", "I-")):
        return label[2:]
    return label


def labels_to_entities(labels: list[str]) -> list[tuple[int, int, str]]:
    entities: list[tuple[int, int, str]] = []
    start: int | None = None
    active = ""

    def close(stop: int) -> None:
        nonlocal start, active
        if start is not None:
            entities.append((start, stop, active))
        start = None
        active = ""

    for index, label in enumerate(labels):
        if label == "O":
            close(index)
            continue
        prefix = label[:1] if label.startswith(("B-", "I-")) else "B"
        base = strip_bio(label)
        if prefix == "B" or start is None or active != base:
            close(index)
            start = index
            active = base
    close(len(labels))
    return entities


def predicted_entity(row: dict[str, Any], start: int, stop: int, label: str) -> dict[str, Any]:
    starts = row.get("token_start_offsets") or []
    ends = row.get("token_end_offsets") or []
    tokens = row.get("tokens") or []
    char_start = int(starts[start]) if start < len(starts) else None
    char_stop = int(ends[stop - 1]) if stop - 1 < len(ends) else None
    text = str(row.get("text") or "")
    if char_start is not None and char_stop is not None and char_start <= char_stop <= len(text):
        surface = text[char_start:char_stop]
    else:
        surface = " ".join(str(token) for token in tokens[start:stop])
    return {
        "label": label,
        "start": char_start,
        "stop": char_stop,
        "surface": surface,
        "token_start": start,
        "token_stop": stop,
    }


def entity_context(text: str, start: int | None, stop: int | None, radius: int = 80) -> tuple[str, str]:
    if start is None or stop is None:
        return "", ""
    left = text[max(0, start - radius) : start].strip()
    right = text[stop : min(len(text), stop + radius)].strip()
    return left, right


def increment(counter: dict[str, int], key: str, amount: int = 1) -> None:
    counter[key] = counter.get(key, 0) + amount


def summarize_predictions(
    source_jsonl: Path,
    predictions_jsonl: Path,
    candidates_jsonl: Path,
    summary_json: Path,
    candidates_tsv: Path | None = None,
) -> dict[str, Any]:
    source_by_id = {row_id(row): row for row in load_jsonl(source_jsonl)}
    prediction_rows = load_jsonl(predictions_jsonl)
    candidates: list[dict[str, Any]] = []
    tsv_rows: list[dict[str, Any]] = []
    by_language: dict[str, int] = {}
    by_label: dict[str, int] = {}
    by_label_language: dict[str, int] = {}
    predicted_entities = 0

    for prediction in prediction_rows:
        doc_id = row_id(prediction)
        source = source_by_id.get(doc_id)
        if source is None:
            continue
        spans = labels_to_entities([str(label) for label in prediction.get("pred_labels", [])])
        if not spans:
            continue
        entities = [predicted_entity(source, start, stop, label) for start, stop, label in spans]
        language = str(source.get("language") or "")
        text = str(source.get("text") or "")
        predicted_entities += len(entities)
        increment(by_language, language)
        for entity in entities:
            label = str(entity["label"])
            increment(by_label, label)
            increment(by_label_language, f"{label}\t{language}")
            left, right = entity_context(text, entity.get("start"), entity.get("stop"))
            tsv_rows.append(
                {
                    "document_id": doc_id,
                    "language": language,
                    "date": source.get("date", ""),
                    "newspaper": source.get("newspaper", ""),
                    "label": label,
                    "surface": entity.get("surface", ""),
                    "start": entity.get("start", ""),
                    "stop": entity.get("stop", ""),
                    "token_start": entity.get("token_start", ""),
                    "token_stop": entity.get("token_stop", ""),
                    "left_context": left,
                    "right_context": right,
                }
            )
        candidates.append(
            {
                "date": source.get("date", ""),
                "document_id": doc_id,
                "language": language,
                "newspaper": source.get("newspaper", ""),
                "predicted_entities": entities,
                "text": text,
                "token_end_offsets": source.get("token_end_offsets", []),
                "token_start_offsets": source.get("token_start_offsets", []),
                "tokens": source.get("tokens", []),
            }
        )

    candidates.sort(key=lambda row: str(row["document_id"]))
    tsv_rows.sort(key=lambda row: (str(row["document_id"]), int(row["token_start"] or 0), str(row["label"])))
    write_jsonl(candidates_jsonl, candidates)
    if candidates_tsv is not None:
        write_tsv(
            candidates_tsv,
            tsv_rows,
            [
                "document_id",
                "language",
                "date",
                "newspaper",
                "label",
                "surface",
                "start",
                "stop",
                "token_start",
                "token_stop",
                "left_context",
                "right_context",
            ],
        )
    summary = {
        "source_jsonl": str(source_jsonl),
        "predictions_jsonl": str(predictions_jsonl),
        "candidates_jsonl": str(candidates_jsonl),
        "candidates_tsv": str(candidates_tsv) if candidates_tsv is not None else "",
        "empty_documents": len(source_by_id),
        "documents_with_predictions": len(candidates),
        "predicted_entities": predicted_entities,
        "documents_with_predictions_by_language": dict(sorted(by_language.items())),
        "predicted_entities_by_label": dict(sorted(by_label.items())),
        "predicted_entities_by_label_language": dict(sorted(by_label_language.items())),
    }
    write_json(summary_json, summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit dataset documents that have no annotated entities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Filter empty-gold documents and add token label ids for classifier evaluation.")
    prepare.add_argument("--input-jsonl", required=True)
    prepare.add_argument("--label-map", required=True)
    prepare.add_argument("--output-jsonl", required=True)
    prepare.add_argument("--summary-json", required=True)

    summarize = subparsers.add_parser("summarize", help="Summarize model predictions on empty-gold documents.")
    summarize.add_argument("--source-jsonl", required=True)
    summarize.add_argument("--predictions-jsonl", required=True)
    summarize.add_argument("--candidates-jsonl", required=True)
    summarize.add_argument("--candidates-tsv", default="")
    summarize.add_argument("--summary-json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.command == "prepare":
        summary = prepare_empty_docs(Path(args.input_jsonl), Path(args.label_map), Path(args.output_jsonl), Path(args.summary_json))
    else:
        summary = summarize_predictions(
            Path(args.source_jsonl),
            Path(args.predictions_jsonl),
            Path(args.candidates_jsonl),
            Path(args.summary_json),
            Path(args.candidates_tsv) if args.candidates_tsv else None,
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
