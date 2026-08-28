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


CONTEXT_SPECS = {
    "ctx512": (512, 256, 32),
    "ctx1024": (1024, 512, 64),
    "ctx2048": (2048, 1024, 128),
}


@dataclass(frozen=True)
class ContextCell:
    context: str
    seed: int
    max_sequence_len: int
    max_words_per_window: int
    stride_words: int
    run_dir: Path
    checkpoint: Path
    source: str
    metrics_path: Path


BASELINE_RESULT_COLUMNS = (
    "entity_precision",
    "entity_recall",
    "entity_f1",
    "token_non_o_f1",
    "entity_correct",
    "entity_gold",
    "entity_pred",
)


def split_words(value: str) -> list[str]:
    return [item for item in value.split() if item]


def selected_contexts(args: argparse.Namespace) -> list[str]:
    contexts = [args.context] if args.context else split_words(args.contexts)
    unsupported = [context for context in contexts if context not in CONTEXT_SPECS]
    if unsupported:
        raise SystemExit(f"unsupported context(s): {' '.join(unsupported)}")
    return contexts


def selected_seeds(args: argparse.Namespace) -> list[int]:
    return [args.seed] if args.seed is not None else [int(seed) for seed in split_words(args.seeds)]


def cell_for(args: argparse.Namespace, context: str, seed: int) -> ContextCell:
    max_sequence_len, max_words_per_window, stride_words = CONTEXT_SPECS[context]
    if context == "ctx512":
        run_dir = Path(args.reused_root) / f"seed-{seed}"
        return ContextCell(
            context=context,
            seed=seed,
            max_sequence_len=max_sequence_len,
            max_words_per_window=max_words_per_window,
            stride_words=stride_words,
            run_dir=run_dir,
            checkpoint=run_dir / "best",
            source="reused",
            metrics_path=run_dir / "eval" / args.decoder / "validation_metrics.json",
        )
    run_dir = Path(args.experiment_root) / context / f"seed-{seed}"
    return ContextCell(
        context=context,
        seed=seed,
        max_sequence_len=max_sequence_len,
        max_words_per_window=max_words_per_window,
        stride_words=stride_words,
        run_dir=run_dir,
        checkpoint=run_dir / "best",
        source="trained",
        metrics_path=run_dir / "eval" / args.decoder / "validation_metrics.json",
    )


def cells(args: argparse.Namespace) -> list[ContextCell]:
    return [cell_for(args, context, seed) for context in selected_contexts(args) for seed in selected_seeds(args)]


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def train_command(args: argparse.Namespace, cell: ContextCell) -> list[str]:
    return [
        args.make_command,
        "train",
        f"CFG={args.cfg}",
        f"MODEL={cell.run_dir}",
        f"SELECTED_MODEL={cell.checkpoint}",
        f"SEED={cell.seed}",
        "LABEL_ALL_TOKENS=true",
        f"DECODER={args.decoder}",
        f"MAX_SEQUENCE_LEN={cell.max_sequence_len}",
        f"MAX_WORDS_PER_WINDOW={cell.max_words_per_window}",
        f"STRIDE_WORDS={cell.stride_words}",
    ]


def evaluate_command(args: argparse.Namespace, cell: ContextCell) -> list[str]:
    eval_dir = cell.run_dir / "eval" / args.decoder
    return [
        args.make_command,
        "evaluate-validation",
        f"CFG={args.cfg}",
        f"MODEL={cell.run_dir}",
        f"SELECTED_MODEL={cell.checkpoint}",
        f"EVAL_OUTPUT_DIR={eval_dir}",
        f"SEED={cell.seed}",
        "LABEL_ALL_TOKENS=true",
        f"DECODER={args.decoder}",
        f"MAX_SEQUENCE_LEN={cell.max_sequence_len}",
        f"MAX_WORDS_PER_WINDOW={cell.max_words_per_window}",
        f"STRIDE_WORDS={cell.stride_words}",
    ]


def run_command(command: list[str], *, execute: bool) -> int:
    print(shell_join(command))
    if not execute:
        return 0
    return subprocess.call(command)


def training_status(cell: ContextCell) -> str:
    if cell.source == "reused":
        return "reused" if (cell.checkpoint / "config.json").is_file() else "missing_reused"
    if (cell.checkpoint / "config.json").is_file():
        return "trained"
    if cell.run_dir.exists():
        return "started"
    return "planned"


def evaluation_status(cell: ContextCell) -> str:
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


def baseline_metrics_from_tsv(args: argparse.Namespace, cell: ContextCell) -> dict[str, Any] | None:
    if cell.source != "reused" or not args.baseline_results_tsv:
        return None
    for row in read_tsv(Path(args.baseline_results_tsv)):
        if (
            row.get("training_supervision") == args.supervision
            and row.get("decoder") == args.decoder
            and row.get("seed") == str(cell.seed)
        ):
            return {column: parse_metric_value(row.get(column)) for column in BASELINE_RESULT_COLUMNS}
    return None


def parse_metric_value(value: str | None) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def manifest(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "experiment": args.experiment_id,
        "cfg": args.cfg,
        "contexts": selected_contexts(args),
        "seeds": selected_seeds(args),
        "training_supervision": args.supervision,
        "decoder": args.decoder,
        "runs": [
            {
                "context": cell.context,
                "seed": cell.seed,
                "source": cell.source,
                "run_dir": str(cell.run_dir),
                "checkpoint": str(cell.checkpoint),
                "metrics": str(cell.metrics_path),
                "max_sequence_len": cell.max_sequence_len,
                "max_words_per_window": cell.max_words_per_window,
                "stride_words": cell.stride_words,
                "training_status": training_status(cell),
                "evaluation_status": (
                    "evaluated_from_baseline_tsv"
                    if baseline_metrics_from_tsv(args, cell)
                    else evaluation_status(cell)
                ),
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


def write_run_metadata(args: argparse.Namespace, cell: ContextCell) -> None:
    cell.run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        cell.run_dir / "experiment_run.json",
        {
            "experiment": args.experiment_id,
            "context": cell.context,
            "seed": cell.seed,
            "source": cell.source,
            "training_supervision": args.supervision,
            "label_all_tokens": True,
            "decoder": args.decoder,
            "cfg": args.cfg,
            "run_dir": str(cell.run_dir),
            "checkpoint": str(cell.checkpoint),
            "max_sequence_len": cell.max_sequence_len,
            "max_words_per_window": cell.max_words_per_window,
            "stride_words": cell.stride_words,
        },
    )


def train(args: argparse.Namespace) -> int:
    status_code = 0
    for cell in cells(args):
        if cell.source == "reused":
            print(f"skip reused baseline: {cell.context} seed-{cell.seed}")
            continue
        if args.resume and training_status(cell) == "trained":
            print(f"skip trained: {cell.context} seed-{cell.seed}")
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
            print(f"skip reused baseline metrics: {cell.context} seed-{cell.seed}")
            continue
        if training_status(cell) != "trained":
            print(f"skip missing checkpoint: {cell.context} seed-{cell.seed}")
            continue
        if args.resume and evaluation_status(cell) == "evaluated":
            print(f"skip evaluated: {cell.context} seed-{cell.seed}")
            continue
        code = run_command(evaluate_command(args, cell), execute=args.execute)
        status_code = status_code or code
        if code:
            break
    write_manifest(args)
    return status_code


def metric_row(args: argparse.Namespace, cell: ContextCell) -> dict[str, Any] | None:
    if cell.metrics_path.is_file():
        metrics = json.loads(cell.metrics_path.read_text(encoding="utf-8"))
    else:
        metrics = baseline_metrics_from_tsv(args, cell)
        if metrics is None:
            return None
    return {
        "experiment": args.experiment_id,
        "context": cell.context,
        "seed": cell.seed,
        "source": cell.source,
        "checkpoint": str(cell.checkpoint),
        "max_sequence_len": cell.max_sequence_len,
        "max_words_per_window": cell.max_words_per_window,
        "stride_words": cell.stride_words,
        "entity_precision": metrics.get("entity_precision"),
        "entity_recall": metrics.get("entity_recall"),
        "entity_f1": metrics.get("entity_f1"),
        "token_non_o_f1": metrics.get("token_non_o_f1"),
        "entity_correct": metrics.get("entity_correct"),
        "entity_gold": metrics.get("entity_gold"),
        "entity_pred": metrics.get("entity_pred"),
    }


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["context"]), []).append(row)
    out = []
    for context, group in sorted(grouped.items(), key=lambda item: CONTEXT_SPECS[item[0]][0]):
        f1s = [float(row["entity_f1"]) for row in group if row.get("entity_f1") is not None]
        precisions = [float(row["entity_precision"]) for row in group if row.get("entity_precision") is not None]
        recalls = [float(row["entity_recall"]) for row in group if row.get("entity_recall") is not None]
        if not f1s:
            continue
        max_sequence_len, max_words_per_window, stride_words = CONTEXT_SPECS[context]
        out.append(
            {
                "context": context,
                "max_sequence_len": max_sequence_len,
                "max_words_per_window": max_words_per_window,
                "stride_words": stride_words,
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


def paired_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_seed_context = {(int(row["seed"]), str(row["context"])): row for row in rows}
    out = []
    for seed in sorted({int(row["seed"]) for row in rows}):
        baseline = by_seed_context.get((seed, "ctx512"))
        row1024 = by_seed_context.get((seed, "ctx1024"))
        row2048 = by_seed_context.get((seed, "ctx2048"))
        item: dict[str, Any] = {"seed": seed}
        if baseline and row1024:
            item["ctx1024_minus_ctx512"] = float(row1024["entity_f1"]) - float(baseline["entity_f1"])
        if baseline and row2048:
            item["ctx2048_minus_ctx512"] = float(row2048["entity_f1"]) - float(baseline["entity_f1"])
        if row1024 and row2048:
            item["ctx2048_minus_ctx1024"] = float(row2048["entity_f1"]) - float(row1024["entity_f1"])
        if len(item) > 1:
            out.append(item)
    if out:
        mean: dict[str, Any] = {"seed": "mean"}
        for key in ("ctx1024_minus_ctx512", "ctx2048_minus_ctx512", "ctx2048_minus_ctx1024"):
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
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(str(row.get(column, "")) for column in columns) + "\n")


def write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"# {summary['experiment']}",
        "",
        "Validation-only context-length experiment. Test evaluation is intentionally not part of this matrix.",
        "",
        "| Context | Max sequence | Max words | Stride | Runs | Entity F1 mean | F1 stdev | Precision mean | Recall mean |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["summary"]:
        lines.append(
            "| {context} | {max_sequence_len} | {max_words_per_window} | {stride_words} | {runs} | "
            "{entity_f1_mean:.6f} | {entity_f1_stdev:.6f} | {entity_precision_mean:.6f} | "
            "{entity_recall_mean:.6f} |".format(**row)
        )
    lines.extend(["", "## Paired Seed Deltas", ""])
    lines.append("| Seed | 1024-512 F1 | 2048-512 F1 | 2048-1024 F1 |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in summary["paired_deltas"]:
        lines.append(
            "| {seed} | {ctx1024_minus_ctx512} | {ctx2048_minus_ctx512} | {ctx2048_minus_ctx1024} |".format(
                seed=row.get("seed", ""),
                ctx1024_minus_ctx512=f"{row['ctx1024_minus_ctx512']:.6f}" if "ctx1024_minus_ctx512" in row else "",
                ctx2048_minus_ctx512=f"{row['ctx2048_minus_ctx512']:.6f}" if "ctx2048_minus_ctx512" in row else "",
                ctx2048_minus_ctx1024=f"{row['ctx2048_minus_ctx1024']:.6f}" if "ctx2048_minus_ctx1024" in row else "",
            )
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def report(args: argparse.Namespace) -> int:
    rows = [row for cell in cells(args) if (row := metric_row(args, cell)) is not None]
    summary = {
        "experiment": args.experiment_id,
        "rows": len(rows),
        "summary": aggregate(rows),
        "paired_deltas": paired_deltas(rows),
    }
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(report_dir / "results.tsv", rows)
    write_tsv(report_dir / "paired_deltas.tsv", summary["paired_deltas"])
    write_manifest(args)
    write_json(report_dir / "results.json", rows)
    write_json(report_dir / "summary.json", summary)
    write_markdown_report(report_dir / "REPORT.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan, run, and summarize context-length experiments.")
    parser.add_argument("mode", choices=["plan", "status", "train", "evaluate", "report"])
    parser.add_argument("--experiment-id", default=os.environ.get("CONTEXT_EXPERIMENT_ID", "context-v2.0.0"))
    parser.add_argument("--cfg", default=os.environ.get("CFG", "configs/experiments/context-v2.0.0.mk"))
    parser.add_argument("--seeds", default=os.environ.get("CONTEXT_EXPERIMENT_SEEDS", "17 42 73"))
    parser.add_argument("--contexts", default=os.environ.get("CONTEXT_EXPERIMENT_CONTEXTS", "ctx512 ctx1024 ctx2048"))
    parser.add_argument("--decoder", default=os.environ.get("CONTEXT_EXPERIMENT_DECODER", "first_subtoken_viterbi"))
    parser.add_argument("--supervision", default=os.environ.get("CONTEXT_EXPERIMENT_SUPERVISION", "all_subtokens_b_to_i"))
    parser.add_argument("--experiment-root", default=os.environ.get("CONTEXT_EXPERIMENT_ROOT", "models.d/experiments/context-v2.0.0"))
    parser.add_argument("--report-dir", default=os.environ.get("CONTEXT_EXPERIMENT_REPORT_DIR", "reports.d/experiments/context-v2.0.0"))
    parser.add_argument("--reused-root", default=os.environ.get("CONTEXT_EXPERIMENT_REUSED_ROOT", "models.d/experiments/decoding-v2.0.0/all_subtokens_b_to_i"))
    parser.add_argument("--baseline-results-tsv", default=os.environ.get("CONTEXT_EXPERIMENT_BASELINE_RESULTS_TSV", "reports.d/experiments/decoding-v2.0.0/results.tsv"))
    parser.add_argument("--context", choices=sorted(CONTEXT_SPECS), default=os.environ.get("CONTEXT_EXPERIMENT_CELL_CONTEXT"))
    parser.add_argument("--seed", type=int, default=int(os.environ["CONTEXT_EXPERIMENT_CELL_SEED"]) if os.environ.get("CONTEXT_EXPERIMENT_CELL_SEED") else None)
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
