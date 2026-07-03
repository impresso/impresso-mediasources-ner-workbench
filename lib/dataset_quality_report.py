from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SPLITS = ("validation", "test")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("document_id") or row.get("id") or "")


def validate_evaluation(
    *, split: str, source_rows: list[dict[str, Any]], prediction_rows: list[dict[str, Any]], metrics: dict[str, Any]
) -> None:
    source_ids = [row_id(row) for row in source_rows]
    prediction_ids = [row_id(row) for row in prediction_rows]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(f"{split}: source contains duplicate document IDs")
    if len(prediction_ids) != len(set(prediction_ids)):
        raise ValueError(f"{split}: predictions contain duplicate document IDs")
    if set(source_ids) != set(prediction_ids):
        missing = sorted(set(source_ids) - set(prediction_ids))
        extra = sorted(set(prediction_ids) - set(source_ids))
        raise ValueError(
            f"{split}: evaluation does not match current dataset; "
            f"missing predictions={len(missing)}, extra predictions={len(extra)}"
        )
    if metrics.get("split") != split:
        raise ValueError(f"{split}: metrics identify split as {metrics.get('split')!r}")
    if int(metrics.get("documents", -1)) != len(source_rows):
        raise ValueError(
            f"{split}: metrics cover {metrics.get('documents')} documents, current dataset has {len(source_rows)}"
        )


def coverage_level(gold: int) -> str:
    if gold >= 50:
        return "adequate"
    if gold >= 20:
        return "limited"
    return "insufficient"


def render_report(results: dict[str, dict[str, Any]], *, release: str, model: str) -> str:
    lines = [
        f"# Validation and Test Quality: {release}",
        "",
        f"Model: `{model}`",
        "",
        "This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.",
        "",
        "Coverage levels: **adequate** = at least 50 gold mentions; **limited** = 20-49; **insufficient** = fewer than 20.",
        "",
        "## Overall Quality",
        "",
        "| Split | Documents | Gold mentions | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for split in SPLITS:
        metrics = results[split]["metrics"]
        lines.append(
            f"| {split} | {metrics['documents']:,} | {metrics['entity_gold']:,} | "
            f"{metrics['entity_precision']:.3f} | {metrics['entity_recall']:.3f} | {metrics['entity_f1']:.3f} |"
        )

    labels = sorted(
        {label for split in SPLITS for label in results[split]["metrics"].get("entity_by_label", {})}
    )
    lines.extend(
        [
            "",
            "## Quality by Entity",
            "",
            "| Entity label | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 | Test coverage |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for label in labels:
        val = results["validation"]["metrics"].get("entity_by_label", {}).get(label, {})
        test = results["test"]["metrics"].get("entity_by_label", {}).get(label, {})
        test_gold = int(test.get("gold", 0))
        lines.append(
            f"| `{label}` | {int(val.get('gold', 0))} | {float(val.get('f1', 0)):.3f} | "
            f"{test_gold} | {float(test.get('precision', 0)):.3f} | {float(test.get('recall', 0)):.3f} | "
            f"{float(test.get('f1', 0)):.3f} | {coverage_level(test_gold)} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a validated Markdown report of validation/test NER quality.")
    for split in SPLITS:
        parser.add_argument(f"--{split}", required=True)
        parser.add_argument(f"--{split}-predictions", required=True)
        parser.add_argument(f"--{split}-metrics", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release", default="unreleased")
    parser.add_argument("--model", required=True)
    args = parser.parse_args(argv)

    results = {}
    for split in SPLITS:
        source_rows = load_jsonl(Path(getattr(args, split)))
        prediction_rows = load_jsonl(Path(getattr(args, f"{split}_predictions")))
        metrics = load_json(Path(getattr(args, f"{split}_metrics")))
        validate_evaluation(split=split, source_rows=source_rows, prediction_rows=prediction_rows, metrics=metrics)
        results[split] = {"metrics": metrics}

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(results, release=args.release, model=args.model), encoding="utf-8")
    print(json.dumps({"output": str(output), "status": "current", "splits": list(SPLITS)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
