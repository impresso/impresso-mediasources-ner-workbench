from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SPLITS = ("validation", "test")
COVERAGE_LEVELS = {"insufficient": 0, "limited": 1, "adequate": 2}
COVERAGE_NAMES = {value: key for key, value in COVERAGE_LEVELS.items()}


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
    if gold >= 20:
        return "adequate"
    if gold >= 10:
        return "limited"
    return "insufficient"


def combined_coverage(*levels: str) -> str:
    return COVERAGE_NAMES[min(COVERAGE_LEVELS[level] for level in levels)]


def training_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_label: dict[str, int] = {}
    mentions = 0
    for row in rows:
        for entity in row.get("entities") or []:
            label = str(entity.get("label") or "")
            if not label:
                continue
            mentions += 1
            by_label[label] = by_label.get(label, 0) + 1
    return {"documents": len(rows), "mentions": mentions, "by_label": dict(sorted(by_label.items()))}


def render_report(results: dict[str, dict[str, Any]], *, release: str, model: str) -> str:
    lines = [
        f"# Validation and Test Quality: {release}",
        "",
        f"Model: `{model}`",
        "",
        "This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.",
        "",
        "Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.",
        "",
        "## Overall Quality",
        "",
        "| Split | Documents | Gold mentions | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    train = results["train"]
    lines.append(f"| train | {train['documents']:,} | {train['mentions']:,} | - | - | - |")
    for split in SPLITS:
        metrics = results[split]["metrics"]
        lines.append(
            f"| {split} | {metrics['documents']:,} | {metrics['entity_gold']:,} | "
            f"{metrics['entity_precision']:.3f} | {metrics['entity_recall']:.3f} | {metrics['entity_f1']:.3f} |"
        )

    test_labels = set(results["test"]["metrics"].get("entity_by_label", {}))
    coverage_rows = []
    for label in sorted(test_labels):
        train_gold = int(train["by_label"].get(label, 0))
        test_gold = int(results["test"]["metrics"].get("entity_by_label", {}).get(label, {}).get("gold", 0))
        train_coverage = coverage_level(train_gold)
        test_coverage = coverage_level(test_gold)
        coverage_rows.append(
            {
                "label": label,
                "train_gold": train_gold,
                "train_coverage": train_coverage,
                "test_gold": test_gold,
                "test_coverage": test_coverage,
                "combined_coverage": combined_coverage(train_coverage, test_coverage),
            }
        )
    coverage_summary = {level: 0 for level in ("adequate", "limited", "insufficient")}
    for row in coverage_rows:
        coverage_summary[row["combined_coverage"]] += 1
    lines.extend(
        [
            "",
            "## Entity Coverage",
            "",
            "Entity coverage assesses whether labels in the test split have enough gold occurrences to support both training and evaluation. Validation does not contribute to coverage. Overall coverage is the weaker of train and test coverage.",
            "",
            "| Overall coverage | Labels |",
            "|---|---:|",
            f"| adequate | {coverage_summary['adequate']} |",
            f"| limited | {coverage_summary['limited']} |",
            f"| insufficient | {coverage_summary['insufficient']} |",
            "",
            "| Entity label | Train occurrences | Train coverage | Test occurrences | Test coverage | Overall coverage |",
            "|---|---:|---|---:|---|---|",
        ]
    )
    for row in coverage_rows:
        lines.append(
            f"| `{row['label']}` | {row['train_gold']} | {row['train_coverage']} | "
            f"{row['test_gold']} | {row['test_coverage']} | **{row['combined_coverage']}** |"
        )

    labels = sorted({*train["by_label"], *(label for split in SPLITS for label in results[split]["metrics"].get("entity_by_label", {}))})
    lines.extend(
        [
            "",
            "## Quality by Entity",
            "",
            "| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in labels:
        val = results["validation"]["metrics"].get("entity_by_label", {}).get(label, {})
        test = results["test"]["metrics"].get("entity_by_label", {}).get(label, {})
        test_gold = int(test.get("gold", 0))
        lines.append(
            f"| `{label}` | {int(train['by_label'].get(label, 0))} | {int(val.get('gold', 0))} | {float(val.get('f1', 0)):.3f} | "
            f"{test_gold} | {float(test.get('precision', 0)):.3f} | {float(test.get('recall', 0)):.3f} | "
            f"{float(test.get('f1', 0)):.3f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a validated Markdown report of validation/test NER quality.")
    parser.add_argument("--train", required=True)
    for split in SPLITS:
        parser.add_argument(f"--{split}", required=True)
        parser.add_argument(f"--{split}-predictions", required=True)
        parser.add_argument(f"--{split}-metrics", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release", default="unreleased")
    parser.add_argument("--model", required=True)
    args = parser.parse_args(argv)

    results = {"train": training_counts(load_jsonl(Path(args.train)))}
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
