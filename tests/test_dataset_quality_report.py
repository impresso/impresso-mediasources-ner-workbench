import pytest

from lib.dataset_quality_report import coverage_level, validate_evaluation


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
    assert coverage_level(19) == "insufficient"
    assert coverage_level(20) == "limited"
    assert coverage_level(50) == "adequate"
