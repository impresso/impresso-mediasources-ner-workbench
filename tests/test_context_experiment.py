from __future__ import annotations

import json
from pathlib import Path

from lib import context_experiment


def parse_args(tmp_path: Path, *extra: str):
    return context_experiment.parse_args(
        [
            "plan",
            "--experiment-id",
            "context-v2.0.0",
            "--cfg",
            "configs/experiments/context-v2.0.0.mk",
            "--seeds",
            "17 42",
            "--contexts",
            "ctx512 ctx1024 ctx2048",
            "--infer-contexts",
            "ctx512 ctx1024 ctx2048",
            "--experiment-root",
            str(tmp_path / "models" / "context"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--reused-root",
            str(tmp_path / "models" / "decoding" / "all_subtokens_b_to_i"),
            "--baseline-results-tsv",
            str(tmp_path / "decoding-results.tsv"),
            "--make-command",
            "make",
            *extra,
        ]
    )


def test_context_cells_reuse_512_baseline_add_inference_only_and_train_longer_contexts(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--seed", "17")

    cells = context_experiment.cells(args)

    assert [(cell.train_context, cell.infer_context, cell.source) for cell in cells] == [
        ("ctx512", "ctx512", "reused"),
        ("ctx512", "ctx1024", "inference_only"),
        ("ctx512", "ctx2048", "inference_only"),
        ("ctx1024", "ctx1024", "trained"),
        ("ctx2048", "ctx2048", "trained"),
    ]
    assert cells[0].checkpoint == tmp_path / "models" / "decoding" / "all_subtokens_b_to_i" / "seed-17" / "best"
    assert cells[1].checkpoint == cells[0].checkpoint
    assert cells[1].eval_dir == tmp_path / "models" / "context" / "train-ctx512" / "infer-ctx1024" / "seed-17" / "eval" / "first_subtoken_viterbi"
    assert cells[3].run_dir == tmp_path / "models" / "context" / "ctx1024" / "seed-17"


def test_context_cells_can_build_full_train_by_infer_matrix(tmp_path: Path) -> None:
    args = parse_args(
        tmp_path,
        "--experiment-id",
        "context-inference-v2.0.0",
        "--experiment-root",
        str(tmp_path / "models" / "context-inference"),
        "--trained-root",
        str(tmp_path / "models" / "context"),
        "--full-matrix",
        "--seed",
        "17",
    )

    cells = context_experiment.cells(args)

    assert [(cell.train_context, cell.infer_context) for cell in cells] == [
        ("ctx512", "ctx512"),
        ("ctx512", "ctx1024"),
        ("ctx512", "ctx2048"),
        ("ctx1024", "ctx512"),
        ("ctx1024", "ctx1024"),
        ("ctx1024", "ctx2048"),
        ("ctx2048", "ctx512"),
        ("ctx2048", "ctx1024"),
        ("ctx2048", "ctx2048"),
    ]
    assert [cell.source for cell in cells] == [
        "reused",
        "inference_only",
        "inference_only",
        "existing",
        "existing",
        "existing",
        "existing",
        "existing",
        "existing",
    ]
    assert cells[4].run_dir == tmp_path / "models" / "context" / "ctx1024" / "seed-17"
    assert cells[4].eval_dir == tmp_path / "models" / "context-inference" / "train-ctx1024" / "infer-ctx1024" / "seed-17" / "eval" / "first_subtoken_viterbi"


def test_train_command_sets_context_window_parameters(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--context", "ctx1024", "--seed", "17")
    cell = context_experiment.cells(args)[0]

    command = context_experiment.train_command(args, cell)

    assert "train" in command
    assert f"MODEL={cell.run_dir}" in command
    assert f"SELECTED_MODEL={cell.checkpoint}" in command
    assert "LABEL_ALL_TOKENS=true" in command
    assert "DECODER=first_subtoken_viterbi" in command
    assert "MAX_SEQUENCE_LEN=1024" in command
    assert "MAX_WORDS_PER_WINDOW=512" in command
    assert "STRIDE_WORDS=64" in command


def test_evaluate_command_uses_matching_context_window_parameters(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--context", "ctx512", "--infer-context", "ctx2048", "--seed", "42")
    cell = context_experiment.cells(args)[0]

    command = context_experiment.evaluate_command(args, cell)

    assert "evaluate-validation" in command
    assert f"EVAL_OUTPUT_DIR={cell.eval_dir}" in command
    assert "MAX_SEQUENCE_LEN=2048" in command
    assert "MAX_WORDS_PER_WINDOW=1024" in command
    assert "STRIDE_WORDS=128" in command


def test_manifest_records_reused_baseline_metrics_path(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--context", "ctx512", "--seed", "17")

    data = context_experiment.manifest(args)

    run = data["runs"][0]
    assert run["source"] == "reused"
    assert run["training_status"] == "missing_reused"
    assert run["metrics"].endswith("seed-17/eval/first_subtoken_viterbi/validation_metrics.json")


def test_reused_baseline_can_read_decoder_experiment_results_tsv(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--context", "ctx512", "--seed", "17")
    (tmp_path / "decoding-results.tsv").write_text(
        "\t".join(
            [
                "experiment",
                "training_supervision",
                "seed",
                "decoder",
                "checkpoint",
                "entity_precision",
                "entity_recall",
                "entity_f1",
                "token_non_o_f1",
                "entity_correct",
                "entity_gold",
                "entity_pred",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "decoding-v2.0.0",
                "all_subtokens_b_to_i",
                "17",
                "first_subtoken_viterbi",
                "unused",
                "0.96",
                "0.91",
                "0.934",
                "0.94",
                "497",
                "545",
                "517",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    cell = context_experiment.cells(args)[0]

    row = context_experiment.metric_row(args, cell)

    assert row is not None
    assert row["source"] == "reused"
    assert row["entity_f1"] == 0.934
    assert context_experiment.manifest(args)["runs"][0]["evaluation_status"] == "evaluated_from_baseline_tsv"


def test_report_includes_context_summary_and_paired_deltas(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--seed", "17")
    for train_context, infer_context, f1 in [
        ("ctx512", "ctx512", 0.90),
        ("ctx512", "ctx1024", 0.91),
        ("ctx512", "ctx2048", 0.905),
        ("ctx1024", "ctx1024", 0.92),
        ("ctx2048", "ctx2048", 0.915),
    ]:
        cell = [
            item
            for item in context_experiment.cells(args)
            if item.train_context == train_context and item.infer_context == infer_context
        ][0]
        cell.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        cell.metrics_path.write_text(
            json.dumps(
                {
                    "entity_precision": f1,
                    "entity_recall": f1,
                    "entity_f1": f1,
                    "token_non_o_f1": f1,
                    "entity_correct": 1,
                    "entity_gold": 1,
                    "entity_pred": 1,
                }
            ),
            encoding="utf-8",
        )

    assert context_experiment.report(args) == 0

    summary = json.loads((tmp_path / "reports" / "summary.json").read_text(encoding="utf-8"))
    assert [(row["train_context"], row["infer_context"]) for row in summary["summary"]] == [
        ("ctx512", "ctx512"),
        ("ctx512", "ctx1024"),
        ("ctx512", "ctx2048"),
        ("ctx1024", "ctx1024"),
        ("ctx2048", "ctx2048"),
    ]
    assert summary["paired_deltas"][0]["ctx512_to_ctx1024_minus_ctx512_to_ctx512"] == 0.010000000000000009
    assert summary["paired_deltas"][0]["ctx1024_to_ctx1024_minus_ctx512_to_ctx512"] == 0.020000000000000018
    assert (tmp_path / "reports" / "paired_deltas.tsv").is_file()
    assert "ctx2048" in (tmp_path / "reports" / "REPORT.md").read_text(encoding="utf-8")
