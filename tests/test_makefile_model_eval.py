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

