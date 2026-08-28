from __future__ import annotations

import json
from pathlib import Path

from lib import decoding_experiment


def parse_args(tmp_path: Path, *extra: str):
    return decoding_experiment.parse_args(
        [
            "plan",
            "--experiment-id",
            "decoding-v2.0.0",
            "--cfg",
            "configs/experiments/decoding-v2.0.0.mk",
            "--seeds",
            "17 42",
            "--supervisions",
            "first_subtoken all_subtokens_b_to_i",
            "--decoders",
            "first_subtoken first_subtoken_viterbi all_subtoken",
            "--experiment-root",
            str(tmp_path / "models"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--make-command",
            "make",
            *extra,
        ]
    )


def test_experiment_cells_use_semantic_supervision_and_seed_paths(tmp_path: Path) -> None:
    args = parse_args(tmp_path)

    cells = decoding_experiment.cells(args)

    assert [(cell.supervision, cell.seed) for cell in cells] == [
        ("first_subtoken", 17),
        ("first_subtoken", 42),
        ("all_subtokens_b_to_i", 17),
        ("all_subtokens_b_to_i", 42),
    ]
    assert cells[0].run_dir == tmp_path / "models" / "first_subtoken" / "seed-17"


def test_train_command_pins_run_identity_and_training_decoder(tmp_path: Path) -> None:
    args = parse_args(tmp_path)
    cell = decoding_experiment.cells(args)[0]

    command = decoding_experiment.train_command(args, cell)

    assert "train" in command
    assert f"MODEL={cell.run_dir}" in command
    assert f"SELECTED_MODEL={cell.run_dir / 'best'}" in command
    assert "SEED=17" in command
    assert "LABEL_ALL_TOKENS=false" in command
    assert "DECODER=first_subtoken_viterbi" in command


def test_evaluate_command_routes_each_decoder_to_own_validation_dir(tmp_path: Path) -> None:
    args = parse_args(tmp_path)
    cell = decoding_experiment.cells(args)[1]

    command = decoding_experiment.evaluate_command(args, cell, "all_subtoken_viterbi")

    assert "evaluate-validation" in command
    assert f"MODEL={cell.run_dir}" in command
    assert f"SELECTED_MODEL={cell.run_dir / 'best'}" in command
    assert f"EVAL_OUTPUT_DIR={cell.run_dir / 'eval' / 'all_subtoken_viterbi'}" in command
    assert "DECODER=all_subtoken_viterbi" in command


def test_manifest_reports_training_and_evaluation_status(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--supervision", "first_subtoken", "--seed", "17")
    cell = decoding_experiment.cells(args)[0]
    (cell.run_dir / "best").mkdir(parents=True)
    (cell.run_dir / "best" / "config.json").write_text("{}", encoding="utf-8")
    eval_dir = cell.run_dir / "eval" / "first_subtoken"
    eval_dir.mkdir(parents=True)
    (eval_dir / "validation_metrics.json").write_text("{}", encoding="utf-8")
    (eval_dir / "validation_predictions.jsonl").write_text("", encoding="utf-8")

    data = decoding_experiment.manifest(args)

    assert data["runs"][0]["training_status"] == "trained"
    assert data["runs"][0]["evaluations"]["first_subtoken"] == "evaluated"
    assert data["runs"][0]["evaluations"]["first_subtoken_viterbi"] == "missing"
    assert data["runs"][0]["evaluations"]["all_subtoken"] == "missing"


def test_manifest_header_preserves_configured_dimensions(tmp_path: Path) -> None:
    args = parse_args(tmp_path)

    data = decoding_experiment.manifest(args)

    assert data["seeds"] == [17, 42]
    assert data["supervisions"] == ["first_subtoken", "all_subtokens_b_to_i"]
    assert data["decoders"] == ["first_subtoken", "first_subtoken_viterbi", "all_subtoken"]


def test_report_writes_machine_and_markdown_outputs(tmp_path: Path) -> None:
    args = parse_args(tmp_path, "--supervision", "first_subtoken", "--seed", "17")
    cell = decoding_experiment.cells(args)[0]
    first_subtoken_dir = cell.run_dir / "eval" / "first_subtoken"
    first_subtoken_dir.mkdir(parents=True)
    (first_subtoken_dir / "validation_metrics.json").write_text(
        json.dumps(
            {
                "entity_precision": 0.86,
                "entity_recall": 0.77,
                "entity_f1": 0.812,
                "token_non_o_f1": 0.78,
                "entity_correct": 9,
                "entity_gold": 12,
                "entity_pred": 10,
            }
        ),
        encoding="utf-8",
    )
    all_subtoken_dir = cell.run_dir / "eval" / "all_subtoken"
    all_subtoken_dir.mkdir(parents=True)
    (all_subtoken_dir / "validation_metrics.json").write_text(
        json.dumps(
            {
                "entity_precision": 0.88,
                "entity_recall": 0.79,
                "entity_f1": 0.833,
                "token_non_o_f1": 0.80,
                "entity_correct": 9,
                "entity_gold": 12,
                "entity_pred": 10,
            }
        ),
        encoding="utf-8",
    )
    eval_dir = cell.run_dir / "eval" / "first_subtoken_viterbi"
    eval_dir.mkdir(parents=True)
    (eval_dir / "validation_metrics.json").write_text(
        json.dumps(
            {
                "entity_precision": 0.9,
                "entity_recall": 0.8,
                "entity_f1": 0.847,
                "token_non_o_f1": 0.81,
                "entity_correct": 10,
                "entity_gold": 12,
                "entity_pred": 11,
            }
        ),
        encoding="utf-8",
    )

    assert decoding_experiment.report(args) == 0

    assert (tmp_path / "reports" / "results.tsv").is_file()
    assert (tmp_path / "reports" / "paired_decoder_deltas.tsv").is_file()
    assert (tmp_path / "reports" / "results.json").is_file()
    assert (tmp_path / "reports" / "summary.json").is_file()
    summary = json.loads((tmp_path / "reports" / "summary.json").read_text(encoding="utf-8"))
    assert summary["paired_decoder_deltas"][0]["first_subtoken_minus_first_subtoken_viterbi"] == -0.03499999999999992
    assert summary["paired_decoder_deltas"][0]["all_subtoken_minus_first_subtoken_viterbi"] == -0.014000000000000012
    report = (tmp_path / "reports" / "REPORT.md").read_text(encoding="utf-8")
    assert "first_subtoken_viterbi" in report
    assert "Paired Decoder Deltas" in report
