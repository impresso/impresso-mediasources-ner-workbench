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
    train_context: str
    infer_context: str
    seed: int
    train_max_sequence_len: int
    train_max_words_per_window: int
    train_stride_words: int
    infer_max_sequence_len: int
    infer_max_words_per_window: int
    infer_stride_words: int
    run_dir: Path
    checkpoint: Path
    eval_dir: Path
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


def selected_infer_contexts(args: argparse.Namespace) -> list[str]:
    contexts = [args.infer_context] if args.infer_context else split_words(args.infer_contexts)
    unsupported = [context for context in contexts if context not in CONTEXT_SPECS]
    if unsupported:
        raise SystemExit(f"unsupported inference context(s): {' '.join(unsupported)}")
    return contexts


def selected_seeds(args: argparse.Namespace) -> list[int]:
    return [args.seed] if args.seed is not None else [int(seed) for seed in split_words(args.seeds)]


def evaluation_dir(args: argparse.Namespace, train_context: str, infer_context: str, seed: int) -> Path:
    if train_context == "ctx512" and infer_context == "ctx512" and not args.full_matrix:
        return Path(args.reused_root) / f"seed-{seed}" / "eval" / args.decoder
    if train_context == infer_context and not args.full_matrix:
        return Path(args.experiment_root) / train_context / f"seed-{seed}" / "eval" / args.decoder
    return Path(args.experiment_root) / f"train-{train_context}" / f"infer-{infer_context}" / f"seed-{seed}" / "eval" / args.decoder


def cell_for(args: argparse.Namespace, train_context: str, infer_context: str, seed: int) -> ContextCell:
    train_max_sequence_len, train_max_words_per_window, train_stride_words = CONTEXT_SPECS[train_context]
    infer_max_sequence_len, infer_max_words_per_window, infer_stride_words = CONTEXT_SPECS[infer_context]
    if train_context == "ctx512":
        run_dir = Path(args.reused_root) / f"seed-{seed}"
        if infer_context == "ctx512":
            source = "reused"
        else:
            source = "inference_only"
        eval_dir = evaluation_dir(args, train_context, infer_context, seed)
        return ContextCell(
            train_context=train_context,
            infer_context=infer_context,
            seed=seed,
            train_max_sequence_len=train_max_sequence_len,
            train_max_words_per_window=train_max_words_per_window,
            train_stride_words=train_stride_words,
            infer_max_sequence_len=infer_max_sequence_len,
            infer_max_words_per_window=infer_max_words_per_window,
            infer_stride_words=infer_stride_words,
            run_dir=run_dir,
            checkpoint=run_dir / "best",
            eval_dir=eval_dir,
            source=source,
            metrics_path=eval_dir / "validation_metrics.json",
        )
    if train_context != infer_context and not args.full_matrix:
        raise SystemExit(f"unsupported unmatched trained context: {train_context}->{infer_context}")
    run_dir = Path(args.trained_root) / train_context / f"seed-{seed}"
    eval_dir = evaluation_dir(args, train_context, infer_context, seed)
    source = "existing" if args.full_matrix else "trained"
    return ContextCell(
        train_context=train_context,
        infer_context=infer_context,
        seed=seed,
        train_max_sequence_len=train_max_sequence_len,
        train_max_words_per_window=train_max_words_per_window,
        train_stride_words=train_stride_words,
        infer_max_sequence_len=infer_max_sequence_len,
        infer_max_words_per_window=infer_max_words_per_window,
        infer_stride_words=infer_stride_words,
        run_dir=run_dir,
        checkpoint=run_dir / "best",
        eval_dir=eval_dir,
        source=source,
        metrics_path=eval_dir / "validation_metrics.json",
    )


def cells(args: argparse.Namespace) -> list[ContextCell]:
    out: list[ContextCell] = []
    infer_contexts = selected_infer_contexts(args)
    for train_context in selected_contexts(args):
        for seed in selected_seeds(args):
            if args.full_matrix:
                for infer_context in infer_contexts:
                    out.append(cell_for(args, train_context, infer_context, seed))
            elif train_context == "ctx512":
                for infer_context in infer_contexts:
                    out.append(cell_for(args, train_context, infer_context, seed))
            else:
                out.append(cell_for(args, train_context, train_context, seed))
    return out


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
        f"MAX_SEQUENCE_LEN={cell.train_max_sequence_len}",
        f"MAX_WORDS_PER_WINDOW={cell.train_max_words_per_window}",
        f"STRIDE_WORDS={cell.train_stride_words}",
    ]


def evaluate_command(args: argparse.Namespace, cell: ContextCell) -> list[str]:
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
        f"MAX_SEQUENCE_LEN={cell.infer_max_sequence_len}",
        f"MAX_WORDS_PER_WINDOW={cell.infer_max_words_per_window}",
        f"STRIDE_WORDS={cell.infer_stride_words}",
    ]


def run_command(command: list[str], *, execute: bool) -> int:
    print(shell_join(command))
    if not execute:
        return 0
    return subprocess.call(command)


def training_status(cell: ContextCell) -> str:
    if cell.source in {"reused", "inference_only"}:
        return "reused" if (cell.checkpoint / "config.json").is_file() else "missing_reused"
    if cell.source == "existing":
        return "trained" if (cell.checkpoint / "config.json").is_file() else "missing_trained"
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
    if cell.source != "reused" or cell.train_context != "ctx512" or cell.infer_context != "ctx512" or not args.baseline_results_tsv:
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
        "infer_contexts": selected_infer_contexts(args),
        "seeds": selected_seeds(args),
        "full_matrix": bool(args.full_matrix),
        "training_supervision": args.supervision,
        "decoder": args.decoder,
        "experiment_root": args.experiment_root,
        "trained_root": args.trained_root,
        "runs": [
            {
                "train_context": cell.train_context,
                "infer_context": cell.infer_context,
                "seed": cell.seed,
                "source": cell.source,
                "run_dir": str(cell.run_dir),
                "checkpoint": str(cell.checkpoint),
                "eval_dir": str(cell.eval_dir),
                "metrics": str(cell.metrics_path),
                "train_max_sequence_len": cell.train_max_sequence_len,
                "train_max_words_per_window": cell.train_max_words_per_window,
                "train_stride_words": cell.train_stride_words,
                "infer_max_sequence_len": cell.infer_max_sequence_len,
                "infer_max_words_per_window": cell.infer_max_words_per_window,
                "infer_stride_words": cell.infer_stride_words,
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
        if cell.source in {"trained", "inference_only"}:
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
            "train_context": cell.train_context,
            "infer_context": cell.infer_context,
            "seed": cell.seed,
            "source": cell.source,
            "training_supervision": args.supervision,
            "label_all_tokens": True,
            "decoder": args.decoder,
            "cfg": args.cfg,
            "run_dir": str(cell.run_dir),
            "checkpoint": str(cell.checkpoint),
            "train_max_sequence_len": cell.train_max_sequence_len,
            "train_max_words_per_window": cell.train_max_words_per_window,
            "train_stride_words": cell.train_stride_words,
            "infer_max_sequence_len": cell.infer_max_sequence_len,
            "infer_max_words_per_window": cell.infer_max_words_per_window,
            "infer_stride_words": cell.infer_stride_words,
        },
    )


def train(args: argparse.Namespace) -> int:
    status_code = 0
    for cell in cells(args):
        if cell.source in {"reused", "inference_only", "existing"}:
            print(f"skip existing model: {cell.train_context}->{cell.infer_context} seed-{cell.seed}")
            continue
        if args.resume and training_status(cell) == "trained":
            print(f"skip trained: {cell.train_context}->{cell.infer_context} seed-{cell.seed}")
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
            print(f"skip reused baseline metrics: {cell.train_context}->{cell.infer_context} seed-{cell.seed}")
            continue
        if training_status(cell) not in {"trained", "reused"}:
            print(f"skip missing checkpoint: {cell.train_context}->{cell.infer_context} seed-{cell.seed}")
            continue
        if args.resume and evaluation_status(cell) == "evaluated":
            print(f"skip evaluated: {cell.train_context}->{cell.infer_context} seed-{cell.seed}")
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
        "train_context": cell.train_context,
        "infer_context": cell.infer_context,
        "seed": cell.seed,
        "source": cell.source,
        "checkpoint": str(cell.checkpoint),
        "train_max_sequence_len": cell.train_max_sequence_len,
        "train_max_words_per_window": cell.train_max_words_per_window,
        "train_stride_words": cell.train_stride_words,
        "infer_max_sequence_len": cell.infer_max_sequence_len,
        "infer_max_words_per_window": cell.infer_max_words_per_window,
        "infer_stride_words": cell.infer_stride_words,
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
        grouped.setdefault((str(row["train_context"]), str(row["infer_context"])), []).append(row)
    out = []
    for (train_context, infer_context), group in sorted(
        grouped.items(), key=lambda item: (CONTEXT_SPECS[item[0][0]][0], CONTEXT_SPECS[item[0][1]][0])
    ):
        f1s = [float(row["entity_f1"]) for row in group if row.get("entity_f1") is not None]
        precisions = [float(row["entity_precision"]) for row in group if row.get("entity_precision") is not None]
        recalls = [float(row["entity_recall"]) for row in group if row.get("entity_recall") is not None]
        if not f1s:
            continue
        train_max_sequence_len, train_max_words_per_window, train_stride_words = CONTEXT_SPECS[train_context]
        infer_max_sequence_len, infer_max_words_per_window, infer_stride_words = CONTEXT_SPECS[infer_context]
        out.append(
            {
                "train_context": train_context,
                "infer_context": infer_context,
                "source": str(group[0].get("source", "")),
                "train_max_sequence_len": train_max_sequence_len,
                "train_max_words_per_window": train_max_words_per_window,
                "train_stride_words": train_stride_words,
                "infer_max_sequence_len": infer_max_sequence_len,
                "infer_max_words_per_window": infer_max_words_per_window,
                "infer_stride_words": infer_stride_words,
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
    by_seed_context = {(int(row["seed"]), str(row["train_context"]), str(row["infer_context"])): row for row in rows}
    out = []
    for seed in sorted({int(row["seed"]) for row in rows}):
        baseline = by_seed_context.get((seed, "ctx512", "ctx512"))
        item: dict[str, Any] = {"seed": seed}
        if baseline:
            for train_context, infer_context in sorted(
                {
                    (str(row["train_context"]), str(row["infer_context"]))
                    for row in rows
                    if int(row["seed"]) == seed and not (row["train_context"] == "ctx512" and row["infer_context"] == "ctx512")
                },
                key=lambda pair: (CONTEXT_SPECS[pair[0]][0], CONTEXT_SPECS[pair[1]][0]),
            ):
                compared = by_seed_context.get((seed, train_context, infer_context))
                if compared:
                    key = f"{train_context}_to_{infer_context}_minus_ctx512_to_ctx512"
                    item[key] = float(compared["entity_f1"]) - float(baseline["entity_f1"])
        if len(item) > 1:
            out.append(item)
    if out:
        mean: dict[str, Any] = {"seed": "mean"}
        keys = sorted({key for row in out for key in row if key != "seed"})
        for key in keys:
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
        "Validation-only context-length experiment. Test evaluation is intentionally not part of this matrix.",
        "",
        "| Train context | Infer context | Source | Train window | Infer window | Runs | Entity F1 mean | F1 stdev | Precision mean | Recall mean |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["summary"]:
        lines.append(
            "| {train_context} | {infer_context} | {source} | {train_max_sequence_len}/{train_max_words_per_window}/{train_stride_words} | "
            "{infer_max_sequence_len}/{infer_max_words_per_window}/{infer_stride_words} | {runs} | "
            "{entity_f1_mean:.6f} | {entity_f1_stdev:.6f} | {entity_precision_mean:.6f} | "
            "{entity_recall_mean:.6f} |".format(**row)
        )
    delta_keys = sorted({key for row in summary["paired_deltas"] for key in row if key != "seed"})
    lines.extend(["", "## Paired Seed Deltas", ""])
    if not delta_keys:
        lines.append("No paired deltas available.")
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return
    lines.append("| Seed | " + " | ".join(delta_keys) + " |")
    lines.append("| --- | " + " | ".join("---:" for _key in delta_keys) + " |")
    for row in summary["paired_deltas"]:
        values = [f"{float(row[key]):.6f}" if key in row else "" for key in delta_keys]
        lines.append("| " + str(row.get("seed", "")) + " | " + " | ".join(values) + " |")
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
    parser.add_argument("--infer-contexts", default=os.environ.get("CONTEXT_EXPERIMENT_INFER_CONTEXTS", "ctx512 ctx1024 ctx2048"))
    parser.add_argument("--decoder", default=os.environ.get("CONTEXT_EXPERIMENT_DECODER", "first_subtoken_viterbi"))
    parser.add_argument("--supervision", default=os.environ.get("CONTEXT_EXPERIMENT_SUPERVISION", "all_subtokens_b_to_i"))
    parser.add_argument("--experiment-root", default=os.environ.get("CONTEXT_EXPERIMENT_ROOT", "models.d/experiments/context-v2.0.0"))
    parser.add_argument("--trained-root", default=os.environ.get("CONTEXT_EXPERIMENT_TRAINED_ROOT"))
    parser.add_argument("--report-dir", default=os.environ.get("CONTEXT_EXPERIMENT_REPORT_DIR", "reports.d/experiments/context-v2.0.0"))
    parser.add_argument("--reused-root", default=os.environ.get("CONTEXT_EXPERIMENT_REUSED_ROOT", "models.d/experiments/decoding-v2.0.0/all_subtokens_b_to_i"))
    parser.add_argument("--baseline-results-tsv", default=os.environ.get("CONTEXT_EXPERIMENT_BASELINE_RESULTS_TSV", "reports.d/experiments/decoding-v2.0.0/results.tsv"))
    parser.add_argument("--context", choices=sorted(CONTEXT_SPECS), default=os.environ.get("CONTEXT_EXPERIMENT_CELL_CONTEXT"))
    parser.add_argument("--infer-context", choices=sorted(CONTEXT_SPECS), default=os.environ.get("CONTEXT_EXPERIMENT_CELL_INFER_CONTEXT"))
    parser.add_argument("--seed", type=int, default=int(os.environ["CONTEXT_EXPERIMENT_CELL_SEED"]) if os.environ.get("CONTEXT_EXPERIMENT_CELL_SEED") else None)
    parser.add_argument("--make-command", default=os.environ.get("MAKE", "make"))
    parser.add_argument("--full-matrix", action="store_true", default=os.environ.get("CONTEXT_EXPERIMENT_FULL_MATRIX", "").lower() == "true")
    parser.add_argument("--execute", action="store_true", help="Actually run generated training/evaluation commands.")
    parser.add_argument("--no-resume", dest="resume", action="store_false", default=True)
    args = parser.parse_args(argv)
    if not args.trained_root:
        args.trained_root = args.experiment_root
    return args


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
