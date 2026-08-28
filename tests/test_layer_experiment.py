from __future__ import annotations

import json
from pathlib import Path

from lib import layer_experiment


def parse_args(tmp_path: Path, *extra: str):
    return layer_experiment.parse_args(
        [
            "plan",
            "--experiment-id",
            "layers-v2.0.0",
            "--cfg",
            "configs/experiments/layers-v2.0.0.mk",
            "--seeds",
            "17 42",
            "--layers",
            "4 8",
            "--experiment-root",
            str(tmp_path / "models" / "layers"),
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


def test_layer_cells_reuse_4_layer_baseline_and_train_8_layer_cells(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--seed", "17")

    cells = layer_experiment.cells(args)

    assert [(cell.layers, cell.seed, cell.source) for cell in cells] == [
        (4, 17, "reused"),
        (8, 17, "trained"),
    ]
    assert cells[0].checkpoint == tmp_path / "models" / "decoding" / "all_subtokens_b_to_i" / "seed-17" / "best"
    assert cells[1].run_dir == tmp_path / "models" / "layers" / "layers8" / "seed-17"


def test_train_command_varies_only_unfrozen_layers_on_fixed_protocol(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--layer", "8", "--seed", "17")
    cell = layer_experiment.cells(args)[0]

    command = layer_experiment.train_command(args, cell)

    assert "train" in command
    assert f"MODEL={cell.run_dir}" in command
    assert f"SELECTED_MODEL={cell.checkpoint}" in command
    assert "SEED=17" in command
    assert "LABEL_ALL_TOKENS=true" in command
    assert "DECODER=first_subtoken_viterbi" in command
    assert "UNFREEZE_TOP_LAYERS=8" in command
    assert "MAX_SEQUENCE_LEN=512" in command
    assert "MAX_WORDS_PER_WINDOW=256" in command
    assert "STRIDE_WORDS=32" in command


def test_evaluate_command_uses_selected_checkpoint_and_validation_dir(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--layer", "8", "--seed", "42")
    cell = layer_experiment.cells(args)[0]

    command = layer_experiment.evaluate_command(args, cell)

    assert "evaluate-validation" in command
    assert f"MODEL={cell.run_dir}" in command
    assert f"SELECTED_MODEL={cell.checkpoint}" in command
    assert f"EVAL_OUTPUT_DIR={cell.eval_dir}" in command
    assert "UNFREEZE_TOP_LAYERS=8" in command


def test_reused_baseline_can_read_decoder_experiment_results_tsv(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--layer", "4", "--seed", "17")
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
    cell = layer_experiment.cells(args)[0]

    row = layer_experiment.metric_row(args, cell)

    assert row is not None
    assert row["source"] == "reused"
    assert row["layers"] == 4
    assert row["entity_f1"] == 0.934
    assert layer_experiment.manifest(args)["runs"][0]["evaluation_status"] == "evaluated_from_baseline_tsv"


def test_report_includes_layer_summary_and_paired_deltas(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--seed", "17")
    (tmp_path / "decoding-results.tsv").write_text(
        "\t".join(
            [
                "training_supervision",
                "seed",
                "decoder",
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
                "all_subtokens_b_to_i",
                "17",
                "first_subtoken_viterbi",
                "0.9",
                "0.9",
                "0.90",
                "0.9",
                "1",
                "1",
                "1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    cell = [item for item in layer_experiment.cells(args) if item.layers == 8][0]
    cell.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    cell.metrics_path.write_text(
        json.dumps(
            {
                "entity_precision": 0.92,
                "entity_recall": 0.91,
                "entity_f1": 0.915,
                "token_non_o_f1": 0.91,
                "entity_correct": 1,
                "entity_gold": 1,
                "entity_pred": 1,
            }
        ),
        encoding="utf-8",
    )

    assert layer_experiment.report(args) == 0

    summary = json.loads((tmp_path / "reports" / "summary.json").read_text(encoding="utf-8"))
    assert [(row["layers"], row["runs"]) for row in summary["summary"]] == [(4, 1), (8, 1)]
    assert summary["paired_layer_deltas"][0]["layers8_minus_layers4"] == 0.015000000000000013
    report = (tmp_path / "reports" / "REPORT.md").read_text(encoding="utf-8")
    assert "Validation-only layer-adaptation experiment" in report
    assert "layers8_minus_layers4" in report
