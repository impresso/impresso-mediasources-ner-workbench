import argparse
from pathlib import Path

import pytest

from lib.build_curation_review import (
    build_disagreements,
    context,
    parse_args,
    selected_split_inputs,
    stable_review_id,
    summarize,
)


def test_build_disagreements_groups_overlap_and_extra_prediction() -> None:
    source_rows = [
        {
            "id": "doc1",
            "language": "de",
            "newspaper": "DTT",
            "date": "1945-01-01",
            "source_file": "fixture.tsv",
            "tokens": ["foo", "Agence", "Havas", "bar", "Reuters"],
            "token_start_offsets": [0, 4, 11, 17, 21],
            "token_end_offsets": [3, 10, 16, 20, 28],
            "text": "foo Agence Havas bar Reuters",
        }
    ]
    prediction_rows = [
        {
            "id": "doc1",
            "gold_labels": ["O", "B-org.ent.pressagency.havas", "I-org.ent.pressagency.havas", "O", "O"],
            "pred_labels": ["O", "B-org.ent.pressagency.afp", "I-org.ent.pressagency.afp", "O", "B-org.ent.pressagency.reuters"],
        }
    ]

    rows = build_disagreements(
        "validation",
        source_rows,
        prediction_rows,
        languages={"de", "fr"},
        context_radius=1,
    )

    assert [row["issue_type"] for row in rows] == ["label_mismatch", "extra_prediction"]
    assert rows[0]["review_id"] == stable_review_id(
        "validation",
        "label_mismatch",
        "doc1",
        (1, 3, "org.ent.pressagency.havas"),
        (1, 3, "org.ent.pressagency.afp"),
    )
    assert rows[0]["gold"]["label"] == "org.ent.pressagency.havas"
    assert rows[0]["prediction"]["label"] == "org.ent.pressagency.afp"
    assert rows[1]["prediction"]["surface"] == "Reuters"
    assert summarize(rows)["by_language"] == {"de": 2}
    assert summarize(rows)["by_status"] == {"todo": 2}


def test_build_disagreements_filters_languages() -> None:
    source_rows = [{"id": "doc1", "language": "lb", "tokens": ["Havas"]}]
    prediction_rows = [{"id": "doc1", "gold_labels": ["B-org.ent.pressagency.havas"], "pred_labels": ["O"]}]

    rows = build_disagreements(
        "test",
        source_rows,
        prediction_rows,
        languages={"de", "fr"},
        context_radius=1,
    )

    assert rows == []


def test_build_disagreements_applies_saved_decisions() -> None:
    source_rows = [{"id": "doc1", "language": "de", "tokens": ["Havas"]}]
    prediction_rows = [{"id": "doc1", "gold_labels": ["B-org.ent.pressagency.havas"], "pred_labels": ["O"]}]
    review_id = stable_review_id("validation", "missing_prediction", "doc1", (0, 1, "org.ent.pressagency.havas"), None)

    rows = build_disagreements(
        "validation",
        source_rows,
        prediction_rows,
        languages={"de"},
        context_radius=1,
        decisions={
            review_id: {
                "review_id": review_id,
                "status": "done",
                "choice": "gold",
                "correct_label": "org.ent.pressagency.havas",
                "notes": "gold is correct",
                "reviewer": "tester",
                "reviewed_at": "2026-05-31T12:00:00+02:00",
            }
        },
    )

    assert rows[0]["review_id"] == review_id
    assert rows[0]["decision"]["status"] == "done"
    assert rows[0]["decision"]["choice"] == "gold"
    assert summarize(rows)["by_status"] == {"done": 1}


def test_context_uses_natural_text_offsets_without_synthetic_spaces() -> None:
    source = {
        "tokens": ["D", ".", "N", ".", "B", ".", "Ende"],
        "token_start_offsets": [0, 1, 2, 3, 4, 5, 7],
        "token_end_offsets": [1, 2, 3, 4, 5, 6, 11],
        "token_render": ["NoSpaceAfter", "NoSpaceAfter", "NoSpaceAfter", "NoSpaceAfter", "NoSpaceAfter", "_", "_"],
        "text": "D.N.B. Ende",
    }

    row = context(source, [(0, 6, "org.ent.pressagency.dnb")], radius=1)

    assert row["text"] == "D.N.B. Ende"


def test_selected_split_inputs_accepts_test_only() -> None:
    args = argparse.Namespace(
        splits="test",
        train_jsonl="",
        train_predictions="",
        validation_jsonl="",
        validation_predictions="",
        test_jsonl="test.jsonl",
        test_predictions="test_predictions.jsonl",
    )

    assert selected_split_inputs(args) == [("test", Path("test.jsonl"), Path("test_predictions.jsonl"))]


def test_selected_split_inputs_accepts_train_only() -> None:
    args = argparse.Namespace(
        splits="train",
        train_jsonl="train.jsonl",
        train_predictions="train_predictions.jsonl",
        validation_jsonl="",
        validation_predictions="",
        test_jsonl="",
        test_predictions="",
    )

    assert selected_split_inputs(args) == [("train", Path("train.jsonl"), Path("train_predictions.jsonl"))]


def test_selected_split_inputs_requires_requested_paths() -> None:
    args = argparse.Namespace(
        splits="validation",
        train_jsonl="train.jsonl",
        train_predictions="train_predictions.jsonl",
        validation_jsonl="",
        validation_predictions="",
        test_jsonl="test.jsonl",
        test_predictions="test_predictions.jsonl",
    )

    with pytest.raises(ValueError, match="validation requires"):
        selected_split_inputs(args)


def test_parse_args_defaults_to_all_dataset_splits() -> None:
    args = parse_args(["--output-dir", "review"])

    assert args.splits == "train validation test"
