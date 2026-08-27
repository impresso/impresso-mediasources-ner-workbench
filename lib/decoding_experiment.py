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


SUPERVISION_TO_LABEL_ALL_TOKENS = {
    "first_subtoken": "false",
    "all_subtokens_b_to_i": "true",
}


@dataclass(frozen=True)
class ExperimentCell:
    supervision: str
    seed: int
    run_dir: Path


def split_words(value: str) -> list[str]:
    return [item for item in value.split() if item]


def cells(args: argparse.Namespace) -> list[ExperimentCell]:
    selected_supervisions = [args.supervision] if args.supervision else split_words(args.supervisions)
    selected_seeds = [args.seed] if args.seed is not None else [int(seed) for seed in split_words(args.seeds)]
    out: list[ExperimentCell] = []
    for supervision in selected_supervisions:
        if supervision not in SUPERVISION_TO_LABEL_ALL_TOKENS:
            raise SystemExit(f"unsupported supervision: {supervision}")
        for seed in selected_seeds:
            out.append(
                ExperimentCell(
                    supervision=supervision,
                    seed=seed,
                    run_dir=Path(args.experiment_root) / supervision / f"seed-{seed}",
                )
            )
    return out


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def command_base(args: argparse.Namespace) -> list[str]:
    return [args.make_command]


def train_command(args: argparse.Namespace, cell: ExperimentCell) -> list[str]:
    return [
        *command_base(args),
        "train",
        f"CFG={args.cfg}",
        f"MODEL={cell.run_dir}",
        f"SELECTED_MODEL={cell.run_dir / 'best'}",
        f"SEED={cell.seed}",
        f"LABEL_ALL_TOKENS={SUPERVISION_TO_LABEL_ALL_TOKENS[cell.supervision]}",
        f"DECODER={args.train_decoder}",
    ]


def evaluate_command(args: argparse.Namespace, cell: ExperimentCell, decoder: str) -> list[str]:
    eval_dir = cell.run_dir / "eval" / decoder
    return [
        *command_base(args),
        "evaluate-validation",
        f"CFG={args.cfg}",
        f"MODEL={cell.run_dir}",
        f"SELECTED_MODEL={cell.run_dir / 'best'}",
        f"EVAL_OUTPUT_DIR={eval_dir}",
        f"SEED={cell.seed}",
        f"LABEL_ALL_TOKENS={SUPERVISION_TO_LABEL_ALL_TOKENS[cell.supervision]}",
        f"DECODER={decoder}",
    ]


def run_command(command: list[str], *, execute: bool) -> int:
    print(shell_join(command))
    if not execute:
        return 0
    return subprocess.call(command)


def training_status(cell: ExperimentCell) -> str:
    if (cell.run_dir / "best" / "config.json").is_file():
        return "trained"
    if cell.run_dir.exists():
        return "started"
    return "planned"


def evaluation_status(cell: ExperimentCell, decoder: str) -> str:
    metrics = cell.run_dir / "eval" / decoder / "validation_metrics.json"
    predictions = cell.run_dir / "eval" / decoder / "validation_predictions.jsonl"
    return "evaluated" if metrics.is_file() and predictions.is_file() else "missing"


def manifest(args: argparse.Namespace) -> dict[str, Any]:
    rows = []
    decoders = split_words(args.decoders)
    selected_supervisions = [args.supervision] if args.supervision else split_words(args.supervisions)
    selected_seeds = [args.seed] if args.seed is not None else [int(seed) for seed in split_words(args.seeds)]
    for cell in cells(args):
        rows.append(
            {
                "experiment": args.experiment_id,
                "training_supervision": cell.supervision,
                "seed": cell.seed,
                "run_dir": str(cell.run_dir),
                "training_status": training_status(cell),
                "evaluations": {
                    decoder: evaluation_status(cell, decoder)
                    for decoder in decoders
                },
            }
        )
    return {
        "experiment": args.experiment_id,
        "cfg": args.cfg,
        "seeds": selected_seeds,
        "supervisions": selected_supervisions,
        "decoders": decoders,
        "train_decoder": args.train_decoder,
        "runs": rows,
    }


def write_outputs(args: argparse.Namespace, data: dict[str, Any]) -> None:
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "manifest.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def status(args: argparse.Namespace) -> int:
    data = manifest(args)
    write_outputs(args, data)
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def plan(args: argparse.Namespace) -> int:
    data = manifest(args)
    write_outputs(args, data)
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    print("Training commands:")
    for cell in cells(args):
        print(shell_join(train_command(args, cell)))
    print("Validation evaluation commands:")
    for cell in cells(args):
        for decoder in split_words(args.decoders):
            print(shell_join(evaluate_command(args, cell, decoder)))
    return 0


def train(args: argparse.Namespace) -> int:
    status = 0
    for cell in cells(args):
        if args.resume and training_status(cell) == "trained":
            print(f"skip trained: {cell.supervision} seed-{cell.seed}")
            continue
        write_run_metadata(args, cell)
        code = run_command(train_command(args, cell), execute=args.execute)
        status = status or code
        if code:
            break
    write_outputs(args, manifest(args))
    return status


def write_run_metadata(args: argparse.Namespace, cell: ExperimentCell) -> None:
    cell.run_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "experiment": args.experiment_id,
        "training_supervision": cell.supervision,
        "label_all_tokens": SUPERVISION_TO_LABEL_ALL_TOKENS[cell.supervision],
        "seed": cell.seed,
        "train_decoder": args.train_decoder,
        "cfg": args.cfg,
        "run_dir": str(cell.run_dir),
    }
    (cell.run_dir / "experiment_run.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def evaluate(args: argparse.Namespace) -> int:
    status = 0
    for cell in cells(args):
        if training_status(cell) != "trained":
            print(f"skip missing checkpoint: {cell.supervision} seed-{cell.seed}")
            continue
        for decoder in split_words(args.decoders):
            if args.resume and evaluation_status(cell, decoder) == "evaluated":
                print(f"skip evaluated: {cell.supervision} seed-{cell.seed} {decoder}")
                continue
            code = run_command(evaluate_command(args, cell, decoder), execute=args.execute)
            status = status or code
            if code:
                break
    write_outputs(args, manifest(args))
    return status


def metric_row(args: argparse.Namespace, cell: ExperimentCell, decoder: str) -> dict[str, Any] | None:
    path = cell.run_dir / "eval" / decoder / "validation_metrics.json"
    if not path.is_file():
        return None
    metrics = json.loads(path.read_text(encoding="utf-8"))
    return {
        "experiment": args.experiment_id,
        "training_supervision": cell.supervision,
        "seed": cell.seed,
        "decoder": decoder,
        "checkpoint": str(cell.run_dir / "best"),
        "entity_precision": metrics.get("entity_precision"),
        "entity_recall": metrics.get("entity_recall"),
        "entity_f1": metrics.get("entity_f1"),
        "token_non_o_f1": metrics.get("token_non_o_f1"),
        "entity_correct": metrics.get("entity_correct"),
        "entity_gold": metrics.get("entity_gold"),
        "entity_pred": metrics.get("entity_pred"),
    }


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((str(row["training_supervision"]), str(row["decoder"])), []).append(row)
    out = []
    for (supervision, decoder), group in sorted(grouped.items()):
        f1s = [float(row["entity_f1"]) for row in group if row.get("entity_f1") is not None]
        precisions = [float(row["entity_precision"]) for row in group if row.get("entity_precision") is not None]
        recalls = [float(row["entity_recall"]) for row in group if row.get("entity_recall") is not None]
        if not f1s:
            continue
        out.append(
            {
                "training_supervision": supervision,
                "decoder": decoder,
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


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns = list(rows[0])
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(str(row.get(column, "")) for column in columns) + "\n")


def write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"# {summary['experiment']}",
        "",
        "Validation-only decoder/supervision experiment. Test evaluation is intentionally not part of this matrix.",
        "",
        "| Training supervision | Decoder | Runs | Entity F1 mean | F1 stdev | Precision mean | Recall mean |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["summary"]:
        lines.append(
            "| {training_supervision} | {decoder} | {runs} | {entity_f1_mean:.6f} | "
            "{entity_f1_stdev:.6f} | {entity_precision_mean:.6f} | {entity_recall_mean:.6f} |".format(
                **row
            )
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def report(args: argparse.Namespace) -> int:
    rows = [
        row
        for cell in cells(args)
        for decoder in split_words(args.decoders)
        if (row := metric_row(args, cell, decoder)) is not None
    ]
    summary = {
        "experiment": args.experiment_id,
        "rows": len(rows),
        "summary": aggregate(rows),
    }
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(report_dir / "results.tsv", rows)
    write_outputs(args, manifest(args))
    (report_dir / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (report_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown_report(report_dir / "REPORT.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan, run, and summarize decoder/supervision experiments.")
    parser.add_argument("mode", choices=["plan", "status", "train", "evaluate", "report"])
    parser.add_argument("--experiment-id", default=os.environ.get("EXPERIMENT_ID", "decoding-v2.0.0"))
    parser.add_argument("--cfg", default=os.environ.get("CFG", "configs/experiments/decoding-v2.0.0.mk"))
    parser.add_argument("--seeds", default=os.environ.get("EXPERIMENT_SEEDS", "17 42 73"))
    parser.add_argument("--supervisions", default=os.environ.get("EXPERIMENT_SUPERVISION", "first_subtoken all_subtokens_b_to_i"))
    parser.add_argument("--decoders", default=os.environ.get("EXPERIMENT_DECODERS", "first_subtoken first_subtoken_viterbi all_subtoken_viterbi"))
    parser.add_argument("--train-decoder", default=os.environ.get("EXPERIMENT_TRAIN_DECODER", "first_subtoken_viterbi"))
    parser.add_argument("--experiment-root", default=os.environ.get("EXPERIMENT_ROOT", "models.d/experiments/decoding-v2.0.0"))
    parser.add_argument("--report-dir", default=os.environ.get("EXPERIMENT_REPORT_DIR", "reports.d/experiments/decoding-v2.0.0"))
    parser.add_argument("--supervision", choices=sorted(SUPERVISION_TO_LABEL_ALL_TOKENS), default=os.environ.get("EXPERIMENT_CELL_SUPERVISION"))
    parser.add_argument("--seed", type=int, default=int(os.environ["EXPERIMENT_CELL_SEED"]) if os.environ.get("EXPERIMENT_CELL_SEED") else None)
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
