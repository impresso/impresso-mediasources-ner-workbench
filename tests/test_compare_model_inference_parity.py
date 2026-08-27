from __future__ import annotations

from lib.compare_model_inference_parity import compare_rows, metrics_for, prediction_labels_by_id


class FakePipeline:
    def __init__(self, labels_by_text: dict[str, list[str]]):
        self.labels_by_text = labels_by_text

    def __call__(self, text: str):
        tokens = text.split()
        return {"tokens": tokens, "token_labels": self.labels_by_text[text]}


def test_compare_rows_accepts_exact_decoded_label_parity() -> None:
    rows = [
        {
            "id": "doc-1",
            "text": "Reuters reported",
            "tokens": ["Reuters", "reported"],
            "token_labels": ["B-org.ent.pressagency.reuters", "O"],
        }
    ]
    predictions = [{"id": "doc-1", "pred_labels": ["B-org.ent.pressagency.reuters", "O"]}]

    pipeline_pred_by_id, mismatches = compare_rows(
        rows,
        prediction_labels_by_id(predictions),
        FakePipeline({"Reuters reported": ["B-org.ent.pressagency.reuters", "O"]}),
    )

    assert mismatches == []
    assert metrics_for(rows, pipeline_pred_by_id) == metrics_for(rows, prediction_labels_by_id(predictions))


def test_compare_rows_reports_first_decoded_label_difference() -> None:
    rows = [
        {
            "id": "doc-1",
            "text": "Agence France Presse",
            "tokens": ["Agence", "France", "Presse"],
            "token_labels": ["O", "O", "O"],
        }
    ]
    predictions = [{"id": "doc-1", "pred_labels": ["B-afp", "I-afp", "I-ap"]}]

    _pipeline_pred_by_id, mismatches = compare_rows(
        rows,
        prediction_labels_by_id(predictions),
        FakePipeline({"Agence France Presse": ["B-afp", "I-afp", "B-wolff"]}),
    )

    assert mismatches == [
        {
            "id": "doc-1",
            "kind": "label_mismatch",
            "token_index": 2,
            "token": "Presse",
            "reference_label": "I-ap",
            "pipeline_label": "B-wolff",
        }
    ]
