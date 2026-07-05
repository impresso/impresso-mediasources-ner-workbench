import pytest

from lib.dataset_quality_report import coverage_level, render_report, training_counts, validate_evaluation


def test_validate_evaluation_requires_exact_current_document_set() -> None:
    with pytest.raises(ValueError, match="does not match current dataset"):
        validate_evaluation(
            split="test",
            source_rows=[{"document_id": "doc-1"}, {"document_id": "doc-2"}],
            prediction_rows=[{"id": "doc-1"}],
            metrics={"split": "test", "documents": 1},
        )


def test_validate_evaluation_accepts_current_complete_evaluation() -> None:
    validate_evaluation(
        split="validation",
        source_rows=[{"document_id": "doc-1"}, {"document_id": "doc-2"}],
        prediction_rows=[{"id": "doc-2"}, {"id": "doc-1"}],
        metrics={"split": "validation", "documents": 2},
    )


def test_coverage_levels_are_explicit() -> None:
    assert coverage_level(9) == "insufficient"
    assert coverage_level(10) == "limited"
    assert coverage_level(19) == "limited"
    assert coverage_level(20) == "adequate"


def test_quality_report_includes_training_counts_and_train_only_labels() -> None:
    label = "org.ent.pressagency.spk-smp"
    train = training_counts([{"entities": [{"label": label}]}, {"entities": [{"label": label}]}])
    empty_metrics = {
        "documents": 1,
        "entity_gold": 0,
        "entity_precision": 0.0,
        "entity_recall": 0.0,
        "entity_f1": 0.0,
        "entity_by_label": {},
    }

    report = render_report(
        {"train": train, "validation": {"metrics": empty_metrics}, "test": {"metrics": empty_metrics}},
        release="v2.0.0",
        model="model",
    )

    assert "| train | 2 | 2 | - | - | - |" in report
    assert f"| `{label}` | 2 | 0 | 0.000 | 0 |" in report
