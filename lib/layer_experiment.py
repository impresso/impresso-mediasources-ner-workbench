from __future__ import annotations

import argparse
import json
import os
import shlex
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASELINE_RESULT_COLUMNS = (
    "entity_precision",
    "entity_recall",
    "entity_f1",
    "token_non_o_f1",
    "entity_correct",
    "entity_gold",
    "entity_pred",
)


@dataclass(frozen=True)
class LayerCell:
    layers: int
    seed: int
    run_dir: Path
    checkpoint: Path
    eval_dir: Path
    source: str
    metrics_path: Path


def split_words(value: str) -> list[str]:
    return [item for item in value.split() if item]


def selected_layers(args: argparse.Namespace) -> list[int]:
    return [args.layer] if args.layer is not None else [int(layer) for layer in split_words(args.layers)]


def selected_seeds(args: argparse.Namespace) -> list[int]:
    return [args.seed] if args.seed is not None else [int(seed) for seed in split_words(args.seeds)]


def cell_for(args: argparse.Namespace, layers: int, seed: int) -> LayerCell:
    if layers == args.baseline_layers:
        run_dir = Path(args.reused_root) / f"seed-{seed}"
        eval_dir = run_dir / "eval" / args.decoder
        return LayerCell(
            layers=layers,
            seed=seed,
            run_dir=run_dir,
            checkpoint=run_dir / "best",
            eval_dir=eval_dir,
            source="reused",
            metrics_path=eval_dir / "validation_metrics.json",
        )
    run_dir = Path(args.experiment_root) / f"layers{layers}" / f"seed-{seed}"
    eval_dir = run_dir / "eval" / args.decoder
    return LayerCell(
        layers=layers,
        seed=seed,
        run_dir=run_dir,
        checkpoint=run_dir / "best",
        eval_dir=eval_dir,
        source="trained",
        metrics_path=eval_dir / "validation_metrics.json",
    )


def cells(args: argparse.Namespace) -> list[LayerCell]:
    return [cell_for(args, layers, seed) for layers in selected_layers(args) for seed in selected_seeds(args)]


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def train_command(args: argparse.Namespace, cell: LayerCell) -> list[str]:
    return [
        args.make_command,
        "train",
        f"CFG={args.cfg}",
        f"MODEL={cell.run_dir}",
        f"SELECTED_MODEL={cell.checkpoint}",
        f"SEED={cell.seed}",
        "LABEL_ALL_TOKENS=true",
        f"DECODER={args.decoder}",
        f"UNFREEZE_TOP_LAYERS={cell.layers}",
        "MAX_SEQUENCE_LEN=512",
        "MAX_WORDS_PER_WINDOW=256",
        "STRIDE_WORDS=32",
    ]


def evaluate_command(args: argparse.Namespace, cell: LayerCell) -> list[str]:
    return [
        args.make_command,
        "evaluate-validation",
        f"CFG={args.cfg}",
        f"MODEL={cell.run_dir}",
        f"SELECTED_MODEL={cell.checkpoint}",
        f"EVAL_OUTPUT_DIR={cell.eval_dir}",
        f"SEED={cell.seed}",
        "LABEL_ALL_TOKENS=true",
        f"DECODER={args.decoder}",
        f"UNFREEZE_TOP_LAYERS={cell.layers}",
        "MAX_SEQUENCE_LEN=512",
        "MAX_WORDS_PER_WINDOW=256",
        "STRIDE_WORDS=32",
    ]


def run_command(command: list[str], *, execute: bool) -> int:
    print(shell_join(command))
    if not execute:
        return 0
    return subprocess.call(command)


def training_status(cell: LayerCell) -> str:
    if cell.source == "reused":
        return "reused" if (cell.checkpoint / "config.json").is_file() else "missing_reused"
    if (cell.checkpoint / "config.json").is_file():
        return "trained"
    if cell.run_dir.exists():
        return "started"
    return "planned"


def evaluation_status(cell: LayerCell, args: argparse.Namespace) -> str:
    if baseline_metrics_from_tsv(args, cell) is not None:
        return "evaluated_from_baseline_tsv"
    predictions = cell.metrics_path.parent / "validation_predictions.jsonl"
    return "evaluated" if cell.metrics_path.is_file() and predictions.is_file() else "missing"


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    lines = [line.rstrip("\n").split("\t") for line in path.read_text(encoding="utf-8").splitlines()]
    if not lines:
        return []
    header = lines[0]
    return [dict(zip(header, values, strict=False)) for values in lines[1:] if values]


def parse_metric_value(value: str | None) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def baseline_metrics_from_tsv(args: argparse.Namespace, cell: LayerCell) -> dict[str, Any] | None:
    if cell.layers != args.baseline_layers or not args.baseline_results_tsv:
        return None
    for row in read_tsv(Path(args.baseline_results_tsv)):
        if (
            row.get("training_supervision") == "all_subtokens_b_to_i"
            and row.get("decoder") == args.decoder
            and row.get("seed") == str(cell.seed)
        ):
            return {column: parse_metric_value(row.get(column)) for column in BASELINE_RESULT_COLUMNS}
    return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def manifest(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "experiment": args.experiment_id,
        "cfg": args.cfg,
        "layers": selected_layers(args),
        "baseline_layers": args.baseline_layers,
        "seeds": selected_seeds(args),
        "training_supervision": "all_subtokens_b_to_i",
        "decoder": args.decoder,
        "window": "512/256/32",
        "experiment_root": args.experiment_root,
        "reused_root": args.reused_root,
        "runs": [
            {
                "layers": cell.layers,
                "seed": cell.seed,
                "source": cell.source,
                "run_dir": str(cell.run_dir),
                "checkpoint": str(cell.checkpoint),
                "eval_dir": str(cell.eval_dir),
                "metrics": str(cell.metrics_path),
                "training_status": training_status(cell),
                "evaluation_status": evaluation_status(cell, args),
            }
            for cell in cells(args)
        ],
    }


def write_manifest(args: argparse.Namespace) -> None:
    write_json(Path(args.report_dir) / "manifest.json", manifest(args))


def status(args: argparse.Namespace) -> int:
    data = manifest(args)
    write_json(Path(args.report_dir) / "manifest.json", data)
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def plan(args: argparse.Namespace) -> int:
    status(args)
    print("Training commands:")
    for cell in cells(args):
        if cell.source == "trained":
            print(shell_join(train_command(args, cell)))
    print("Validation evaluation commands:")
    for cell in cells(args):
        if cell.source == "trained":
            print(shell_join(evaluate_command(args, cell)))
    print("Reused baseline metrics:")
    for cell in cells(args):
        if cell.source == "reused":
            print(str(cell.metrics_path))
    return 0


def write_run_metadata(args: argparse.Namespace, cell: LayerCell) -> None:
    cell.run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        cell.run_dir / "experiment_run.json",
        {
            "experiment": args.experiment_id,
            "layers": cell.layers,
            "seed": cell.seed,
            "source": cell.source,
            "training_supervision": "all_subtokens_b_to_i",
            "label_all_tokens": True,
            "decoder": args.decoder,
            "cfg": args.cfg,
            "run_dir": str(cell.run_dir),
            "checkpoint": str(cell.checkpoint),
            "max_sequence_len": 512,
            "max_words_per_window": 256,
            "stride_words": 32,
        },
    )


def train(args: argparse.Namespace) -> int:
    status_code = 0
    for cell in cells(args):
        if cell.source == "reused":
            print(f"skip reused baseline model: layers{cell.layers} seed-{cell.seed}")
            continue
        if args.resume and training_status(cell) == "trained":
            print(f"skip trained: layers{cell.layers} seed-{cell.seed}")
            continue
        write_run_metadata(args, cell)
        code = run_command(train_command(args, cell), execute=args.execute)
        status_code = status_code or code
        if code:
            break
    write_manifest(args)
    return status_code


def evaluate(args: argparse.Namespace) -> int:
    status_code = 0
    for cell in cells(args):
        if cell.source == "reused":
            print(f"skip reused baseline metrics: layers{cell.layers} seed-{cell.seed}")
            continue
        if training_status(cell) != "trained":
            print(f"skip missing checkpoint: layers{cell.layers} seed-{cell.seed}")
            continue
        if args.resume and evaluation_status(cell, args) == "evaluated":
            print(f"skip evaluated: layers{cell.layers} seed-{cell.seed}")
            continue
        code = run_command(evaluate_command(args, cell), execute=args.execute)
        status_code = status_code or code
        if code:
            break
    write_manifest(args)
    return status_code


def metric_row(args: argparse.Namespace, cell: LayerCell) -> dict[str, Any] | None:
    if cell.metrics_path.is_file():
        metrics = json.loads(cell.metrics_path.read_text(encoding="utf-8"))
    else:
        metrics = baseline_metrics_from_tsv(args, cell)
        if metrics is None:
            return None
    return {
        "experiment": args.experiment_id,
        "layers": cell.layers,
        "seed": cell.seed,
        "source": cell.source,
        "checkpoint": str(cell.checkpoint),
        "training_supervision": "all_subtokens_b_to_i",
        "decoder": args.decoder,
        "max_sequence_len": 512,
        "max_words_per_window": 256,
        "stride_words": 32,
        "entity_precision": metrics.get("entity_precision"),
        "entity_recall": metrics.get("entity_recall"),
        "entity_f1": metrics.get("entity_f1"),
        "token_non_o_f1": metrics.get("token_non_o_f1"),
        "entity_correct": metrics.get("entity_correct"),
        "entity_gold": metrics.get("entity_gold"),
        "entity_pred": metrics.get("entity_pred"),
    }


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(int(row["layers"]), []).append(row)
    out = []
    for layers, group in sorted(grouped.items()):
        f1s = [float(row["entity_f1"]) for row in group if row.get("entity_f1") is not None]
        precisions = [float(row["entity_precision"]) for row in group if row.get("entity_precision") is not None]
        recalls = [float(row["entity_recall"]) for row in group if row.get("entity_recall") is not None]
        if not f1s:
            continue
        out.append(
            {
                "layers": layers,
                "runs": len(f1s),
                "entity_f1_mean": statistics.fmean(f1s),
                "entity_f1_stdev": statistics.stdev(f1s) if len(f1s) > 1 else 0.0,
                "entity_f1_min": min(f1s),
                "entity_f1_max": max(f1s),
                "entity_precision_mean": statistics.fmean(precisions) if precisions else None,
                "entity_recall_mean": statistics.fmean(recalls) if recalls else None,
            }
        )
    return out


def paired_layer_deltas(rows: list[dict[str, Any]], *, baseline_layers: int) -> list[dict[str, Any]]:
    by_seed_layers = {(int(row["seed"]), int(row["layers"])): row for row in rows}
    compared_layers = sorted({int(row["layers"]) for row in rows if int(row["layers"]) != baseline_layers})
    out: list[dict[str, Any]] = []
    for seed in sorted({int(row["seed"]) for row in rows}):
        baseline = by_seed_layers.get((seed, baseline_layers))
        if not baseline or baseline.get("entity_f1") is None:
            continue
        item: dict[str, Any] = {
            "seed": seed,
            "baseline_layers": baseline_layers,
            "baseline_entity_f1": baseline["entity_f1"],
        }
        for layers in compared_layers:
            compared = by_seed_layers.get((seed, layers))
            if compared and compared.get("entity_f1") is not None:
                item[f"layers{layers}_minus_layers{baseline_layers}"] = float(compared["entity_f1"]) - float(baseline["entity_f1"])
        if len(item) > 3:
            out.append(item)
    if out:
        mean: dict[str, Any] = {
            "seed": "mean",
            "baseline_layers": baseline_layers,
            "baseline_entity_f1": "",
        }
        for key in sorted({key for row in out for key in row if key.startswith("layers")}):
            values = [float(row[key]) for row in out if key in row]
            if values:
                mean[key] = statistics.fmean(values)
        out.append(mean)
    return out


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns = list(rows[0])
    for row in rows[1:]:
        for column in row:
            if column not in columns:
                columns.append(column)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(str(row.get(column, "")) for column in columns) + "\n")


def write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"# {summary['experiment']}",
        "",
        "Validation-only layer-adaptation experiment. Test evaluation is intentionally not part of this matrix.",
        "",
        "Fixed protocol: ctx512 window (`512/256/32`), all-subtoken B-to-I supervision, `first_subtoken_viterbi` decoding.",
        "",
        "| Unfrozen top layers | Runs | Entity F1 mean | F1 stdev | Precision mean | Recall mean |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["summary"]:
        lines.append(
            "| {layers} | {runs} | {entity_f1_mean:.6f} | {entity_f1_stdev:.6f} | "
            "{entity_precision_mean:.6f} | {entity_recall_mean:.6f} |".format(**row)
        )
    delta_keys = sorted(
        {
            key
            for row in summary["paired_layer_deltas"]
            for key in row
            if key not in {"seed", "baseline_layers", "baseline_entity_f1"}
        }
    )
    lines.extend(["", "## Paired Layer Deltas", ""])
    if not delta_keys:
        lines.append("No paired layer deltas available.")
    else:
        lines.append("| Seed | Baseline layers | Baseline F1 | " + " | ".join(delta_keys) + " |")
        lines.append("| --- | ---: | ---: | " + " | ".join("---:" for _key in delta_keys) + " |")
        for row in summary["paired_layer_deltas"]:
            values = [f"{float(row[key]):.6f}" if key in row else "" for key in delta_keys]
            baseline_f1 = row.get("baseline_entity_f1", "")
            baseline_f1_text = f"{float(baseline_f1):.6f}" if baseline_f1 != "" else ""
            lines.append(
                "| "
                + str(row.get("seed", ""))
                + " | "
                + str(row.get("baseline_layers", ""))
                + " | "
                + baseline_f1_text
                + " | "
                + " | ".join(values)
                + " |"
            )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def report(args: argparse.Namespace) -> int:
    rows = [row for cell in cells(args) if (row := metric_row(args, cell)) is not None]
    summary = {
        "experiment": args.experiment_id,
        "rows": len(rows),
        "summary": aggregate(rows),
        "paired_layer_deltas": paired_layer_deltas(rows, baseline_layers=args.baseline_layers),
    }
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(report_dir / "results.tsv", rows)
    write_tsv(report_dir / "paired_layer_deltas.tsv", summary["paired_layer_deltas"])
    write_manifest(args)
    write_json(report_dir / "results.json", rows)
    write_json(report_dir / "summary.json", summary)
    write_markdown_report(report_dir / "REPORT.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan, run, and summarize layer-adaptation experiments.")
    parser.add_argument("mode", choices=["plan", "status", "train", "evaluate", "report"])
    parser.add_argument("--experiment-id", default=os.environ.get("LAYER_EXPERIMENT_ID", "layers-v2.0.0"))
    parser.add_argument("--cfg", default=os.environ.get("CFG", "configs/experiments/layers-v2.0.0.mk"))
    parser.add_argument("--seeds", default=os.environ.get("LAYER_EXPERIMENT_SEEDS", "17 42 73"))
    parser.add_argument("--layers", default=os.environ.get("LAYER_EXPERIMENT_LAYERS", "4 8"))
    parser.add_argument("--baseline-layers", type=int, default=int(os.environ.get("LAYER_EXPERIMENT_BASELINE_LAYERS", "4")))
    parser.add_argument("--decoder", default=os.environ.get("LAYER_EXPERIMENT_DECODER", "first_subtoken_viterbi"))
    parser.add_argument("--experiment-root", default=os.environ.get("LAYER_EXPERIMENT_ROOT", "models.d/experiments/layers-v2.0.0"))
    parser.add_argument("--report-dir", default=os.environ.get("LAYER_EXPERIMENT_REPORT_DIR", "reports.d/experiments/layers-v2.0.0"))
    parser.add_argument("--reused-root", default=os.environ.get("LAYER_EXPERIMENT_REUSED_ROOT", "models.d/experiments/decoding-v2.0.0/all_subtokens_b_to_i"))
    parser.add_argument("--baseline-results-tsv", default=os.environ.get("LAYER_EXPERIMENT_BASELINE_RESULTS_TSV", "reports.d/experiments/decoding-v2.0.0/results.tsv"))
    parser.add_argument("--layer", type=int, default=int(os.environ["LAYER_EXPERIMENT_CELL_LAYERS"]) if os.environ.get("LAYER_EXPERIMENT_CELL_LAYERS") else None)
    parser.add_argument("--seed", type=int, default=int(os.environ["LAYER_EXPERIMENT_CELL_SEED"]) if os.environ.get("LAYER_EXPERIMENT_CELL_SEED") else None)
    parser.add_argument("--make-command", default=os.environ.get("MAKE", "make"))
    parser.add_argument("--execute", action="store_true", help="Actually run generated training/evaluation commands.")
    parser.add_argument("--no-resume", dest="resume", action="store_false", default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "plan":
        return plan(args)
    if args.mode == "status":
        return status(args)
    if args.mode == "train":
        return train(args)
    if args.mode == "evaluate":
        return evaluate(args)
    if args.mode == "report":
        return report(args)
    raise AssertionError(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
