from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def target_block(text: str, target: str) -> str:
    pattern = rf"^{re.escape(target)}:.*?(?=^[A-Za-z0-9_.-]+:|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    assert match is not None, f"missing Makefile target: {target}"
    return match.group(0)


def test_model_evaluation_targets_use_selected_checkpoint() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    validation = target_block(text, "evaluate-validation")
    heldout = target_block(text, "evaluate-test")

    assert '--checkpoint "$(SELECTED_MODEL)"' in validation
    assert '--eval-jsonl "$(VALIDATION_JSONL)"' in validation
    assert "--split-name validation" in validation

    assert '--checkpoint "$(SELECTED_MODEL)"' in heldout
    assert '--eval-jsonl "$(TEST_JSONL)"' in heldout
    assert "--split-name test" in heldout


def test_model_evaluation_targets_do_not_force_label_map_sync() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert target_block(text, "evaluate-validation").startswith("evaluate-validation: maybe-sync-label-map")
    assert target_block(text, "evaluate-test").startswith("evaluate-test: maybe-sync-label-map")
    assert target_block(text, "curation-eval-validation").startswith(
        "curation-eval-validation: maybe-sync-label-map"
    )
    assert target_block(text, "curation-eval-test").startswith("curation-eval-test: maybe-sync-label-map")


def test_legacy_evaluation_targets_are_compatibility_aliases() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert target_block(text, "test").strip() == "test: evaluate-validation"
    assert target_block(text, "test-official").strip() == "test-official: evaluate-test"


def test_push_model_uses_selected_checkpoint_and_remote_repo_variable() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    block = target_block(text, "push-model")

    assert '--repo-id "$(HF_MODEL_REPO)"' in block
    assert '--revision "$(HF_MODEL_REVISION)"' in block
    assert '--model "$(SELECTED_MODEL)"' in block
    assert '--run-dir "$(MODEL)"' in block
    assert '--repo-id "$(HF_MODEL)"' not in block
    assert '--model "$(MODEL)"' not in block


def test_inference_parity_target_uses_overrideable_release_artifact_paths() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    block = target_block(text, "compare-model-inference-parity")

    assert '--model "$(MODEL_INFERENCE_PARITY_MODEL)"' in block
    assert '--input-jsonl "$(MODEL_INFERENCE_PARITY_INPUT_JSONL)"' in block
    assert '--evaluator-predictions "$(MODEL_INFERENCE_PARITY_EVALUATOR_PREDICTIONS)"' in block
    assert '--summary-json "$(MODEL_INFERENCE_PARITY_SUMMARY_JSON)"' in block
    assert '--mismatches-jsonl "$(MODEL_INFERENCE_PARITY_MISMATCHES_JSONL)"' in block


def test_smoke_model_inference_target_uses_overrideable_model_source() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    block = target_block(text, "smoke-model-inference")

    assert '--model "$(MODEL_INFERENCE_SMOKE_MODEL)"' in block
    assert "MODEL_INFERENCE_SMOKE_REVISION" in block
    assert '--model "$(SELECTED_MODEL)"' not in block


def test_train_passes_configured_decoder_for_checkpoint_selection() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    block = target_block(text, "train")

    assert "$(TRAIN_DECODER_ARGS)" in block


def test_decoding_experiment_targets_are_wired_through_make_config() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    for target, mode in [
        ("decoding-experiment-plan", "plan"),
        ("decoding-experiment-status", "status"),
        ("decoding-experiment-train", "train"),
        ("decoding-experiment-evaluate", "evaluate"),
        ("decoding-experiment-report", "report"),
    ]:
        block = target_block(text, target)
        assert f"lib.decoding_experiment {mode}" in block
        assert "$(DECODING_EXPERIMENT_ARGS)" in block

    assert "--execute" in target_block(text, "decoding-experiment-train")
    assert "--execute" in target_block(text, "decoding-experiment-evaluate")


def test_context_experiment_targets_are_wired_through_make_config() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    for target, mode in [
        ("context-experiment-plan", "plan"),
        ("context-experiment-status", "status"),
        ("context-experiment-train", "train"),
        ("context-experiment-evaluate", "evaluate"),
        ("context-experiment-report", "report"),
    ]:
        block = target_block(text, target)
        assert f"lib.context_experiment {mode}" in block
        assert "$(CONTEXT_EXPERIMENT_ARGS)" in block

    assert "--execute" in target_block(text, "context-experiment-train")
    assert "--execute" in target_block(text, "context-experiment-evaluate")
