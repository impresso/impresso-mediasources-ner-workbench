from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def base_label(label: str) -> str:
    if label.startswith(("B-", "I-")):
        return label[2:]
    return label


def label_sort_key(label: str) -> tuple[str, int]:
    prefix_order = 0 if label.startswith("B-") else 1
    return base_label(label), prefix_order


def make_label_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, int] | dict[str, str]]:
    observed = {
        str(label)
        for row in rows
        for label in row.get("token_labels", [])
        if str(label) != "O"
    }
    invalid = sorted(label for label in observed if not label.startswith(("B-", "I-")))
    if invalid:
        raise ValueError(f"token labels must use BIO prefixes: {', '.join(invalid)}")
    entity_labels = {base_label(label) for label in observed}
    labels = sorted(
        {
            f"{prefix}-{label}"
            for label in entity_labels
            for prefix in ("B", "I")
        },
        key=label_sort_key,
    )
    label2id = {"O": 0}
    for label in labels:
        label2id[label] = len(label2id)
    id2label = {str(label_id): label for label, label_id in label2id.items()}
    return {"label2id": label2id, "id2label": id2label}


def sync_label_map(input_paths: list[Path], output_path: Path, *, check: bool = False) -> dict[str, Any]:
    rows = [row for path in input_paths for row in load_jsonl(path)]
    label_map = make_label_map(rows)
    summary = {
        "inputs": [str(path) for path in input_paths],
        "output": str(output_path),
        "rows": len(rows),
        "labels": len(label_map["label2id"]),
    }
    payload = json.dumps(label_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if check:
        current = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
        summary["up_to_date"] = current == payload
        if current != payload:
            raise ValueError(f"{output_path} is out of date; run make sync-label-map")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        summary["written"] = True
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Derive label_map.json from minimal JSONL token_labels.")
    parser.add_argument("--input-jsonl", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Fail if the output label map is not up to date.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = sync_label_map(args.input_jsonl, args.output, check=args.check)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
