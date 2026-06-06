import json
from pathlib import Path

from lib.audit_empty_training_docs import prepare_empty_docs, summarize_predictions


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_prepare_empty_docs_filters_rows_and_recreates_label_ids(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    label_map = tmp_path / "label_map.json"
    output = tmp_path / "audit" / "empty.jsonl"
    summary = tmp_path / "audit" / "summary.json"
    label_map.write_text(json.dumps({"label2id": {"O": 0}, "id2label": {"0": "O"}}), encoding="utf-8")
    write_jsonl(
        source,
        [
            {
                "document_id": "with-entity",
                "id": "with-entity",
                "language": "fr",
                "tokens": ["Havas"],
                "token_labels": ["B-org.ent.pressagency.havas"],
                "entities": [{"label": "org.ent.pressagency.havas"}],
            },
            {
                "document_id": "empty",
                "id": "empty",
                "language": "de",
                "tokens": ["foo"],
                "token_labels": ["O"],
                "entities": [],
            },
        ],
    )

    result = prepare_empty_docs(source, label_map, output, summary)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert result["empty_documents"] == 1
    assert rows[0]["document_id"] == "empty"
    assert rows[0]["token_label_ids"] == [0]


def test_summarize_predictions_writes_candidate_spans(tmp_path: Path) -> None:
    source = tmp_path / "empty.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    candidates_tsv = tmp_path / "candidates.tsv"
    summary = tmp_path / "summary.json"
    write_jsonl(
        source,
        [
            {
                "document_id": "doc-1",
                "id": "doc-1",
                "date": "1900-01-01",
                "language": "fr",
                "newspaper": "N",
                "text": "foo Reuters bar",
                "tokens": ["foo", "Reuters", "bar"],
                "token_start_offsets": [0, 4, 12],
                "token_end_offsets": [3, 11, 15],
            }
        ],
    )
    write_jsonl(
        predictions,
        [
            {
                "id": "doc-1",
                "pred_labels": ["O", "B-org.ent.pressagency.reuters", "O"],
            },
            {
                "id": "doc-2",
                "pred_labels": ["O", "O", "O"],
            }
        ],
    )

    result = summarize_predictions(source, predictions, candidates, summary, candidates_tsv)

    rows = [json.loads(line) for line in candidates.read_text(encoding="utf-8").splitlines()]
    tsv_lines = candidates_tsv.read_text(encoding="utf-8").splitlines()
    assert result["documents_with_predictions"] == 1
    assert result["predicted_entities_by_label"] == {"org.ent.pressagency.reuters": 1}
    assert rows[0]["predicted_entities"] == [
        {
            "label": "org.ent.pressagency.reuters",
            "start": 4,
            "stop": 11,
            "surface": "Reuters",
            "token_start": 1,
            "token_stop": 2,
        }
    ]
    assert tsv_lines[0].split("\t") == [
        "document_id",
        "language",
        "date",
        "newspaper",
        "label",
        "surface",
        "start",
        "stop",
        "token_start",
        "token_stop",
        "left_context",
        "right_context",
    ]
    assert len(tsv_lines) == 2
    assert tsv_lines[1].split("\t") == [
        "doc-1",
        "fr",
        "1900-01-01",
        "N",
        "org.ent.pressagency.reuters",
        "Reuters",
        "4",
        "11",
        "1",
        "2",
        "foo",
        "bar",
    ]
