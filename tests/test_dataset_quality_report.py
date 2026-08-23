import pytest

from lib.dataset_quality_report import combined_coverage, coverage_level, render_report, training_counts, validate_evaluation


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
    assert combined_coverage("adequate", "limited") == "limited"
    assert combined_coverage("insufficient", "adequate") == "insufficient"


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
    assert f"| `{label}` | 2 | insufficient |" not in report


def test_quality_report_has_train_test_entity_coverage_for_test_labels_only() -> None:
    weak_train_label = "org.ent.pressagency.akp"
    adequate_label = "org.ent.pressagency.afp"
    train = training_counts(
        [
            {"entities": [{"label": weak_train_label}]},
            *({"entities": [{"label": adequate_label}]} for _ in range(20)),
            *({"entities": [{"label": "org.ent.pressagency.train-only"}]} for _ in range(20)),
        ]
    )
    validation_metrics = {
        "documents": 1,
        "entity_gold": 0,
        "entity_precision": 0.0,
        "entity_recall": 0.0,
        "entity_f1": 0.0,
        "entity_by_label": {
            "org.ent.pressagency.validation-only": {"gold": 20, "f1": 1.0},
        },
    }
    test_metrics = {
        "documents": 1,
        "entity_gold": 40,
        "entity_precision": 0.0,
        "entity_recall": 0.0,
        "entity_f1": 0.0,
        "entity_by_label": {
            weak_train_label: {"gold": 20, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            adequate_label: {"gold": 20, "precision": 1.0, "recall": 1.0, "f1": 1.0},
        },
    }

    report = render_report(
        {"train": train, "validation": {"metrics": validation_metrics}, "test": {"metrics": test_metrics}},
        release="v2.0.0",
        model="model",
    )

    assert "## Entity Coverage" in report
    assert "| adequate | 1 |" in report
    assert "| insufficient | 1 |" in report
    assert f"| `{weak_train_label}` | 1 | insufficient | 20 | adequate | **insufficient** |" in report
    assert f"| `{adequate_label}` | 20 | adequate | 20 | adequate | **adequate** |" in report
    assert "org.ent.pressagency.train-only` | 20 | adequate |" not in report
    assert "org.ent.pressagency.validation-only` |" not in report.split("## Entity Coverage", 1)[1].split("## Quality by Entity", 1)[0]
