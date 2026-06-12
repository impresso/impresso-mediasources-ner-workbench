from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            row["_line_number"] = line_number
            rows.append(row)
    return rows


def tsv_cell(value: Any) -> str:
    return str(value).replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def comment_value(value: Any) -> str:
    return str(value).replace("\r", "\\r").replace("\n", "\\n")


def metadata_comments(row: dict[str, Any], *, split: str) -> list[str]:
    comments = [
        ("doc_id", row.get("id", "")),
        ("document_id", row.get("document_id", row.get("id", ""))),
        ("split", row.get("split", split)),
        ("language", row.get("language", "")),
        ("newspaper", row.get("newspaper", "")),
        ("date", row.get("date", "")),
    ]
    return [f"# {key} = {comment_value(value)}" for key, value in comments if value not in {None, ""}]


def iter_conll_rows(rows: Iterable[dict[str, Any]], *, split: str) -> Iterable[str]:
    for row in rows:
        row_id = row.get("id", f"line:{row.get('_line_number', '?')}")
        tokens = row.get("tokens")
        labels = row.get("token_labels")
        if not isinstance(tokens, list):
            raise ValueError(f"{row_id}: missing or invalid tokens")
        if not isinstance(labels, list):
            raise ValueError(f"{row_id}: missing or invalid token_labels")
        if len(tokens) != len(labels):
            raise ValueError(f"{row_id}: tokens/token_labels length mismatch: {len(tokens)} != {len(labels)}")

        yield from metadata_comments(row, split=split)
        yield "TOKEN\tNERTAG"
        for token, label in zip(tokens, labels, strict=True):
            yield f"{tsv_cell(token)}\t{tsv_cell(label)}"
        yield ""


def materialize(input_path: Path, output_path: Path, *, split: str) -> dict[str, Any]:
    rows = load_jsonl(input_path)
    rows = sorted(rows, key=row_sort_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(iter_conll_rows(rows, split=split)) + "\n", encoding="utf-8")
    return {"input": str(input_path), "output": str(output_path), "rows": len(rows), "split": split}


def row_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    document_id = str(row.get("document_id") or row.get("id") or "")
    row_id = str(row.get("id") or "")
    return document_id.casefold(), document_id, row_id.casefold(), row_id


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize a minimal JSONL NER split as CoNLL-like TOKEN/NERTAG TSV.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    split = args.split or args.input.stem
    summary = materialize(args.input, args.output, split=split)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
