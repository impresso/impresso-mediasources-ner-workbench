from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINING_SRC = ROOT / "training" / "newsagency-radiostation-modernbert-classifier" / "src"
sys.path.insert(0, str(TRAINING_SRC))

from mediaagency_modernbert.data import labels_to_entities, load_jsonl, make_windows
from mediaagency_modernbert.metrics import entity_metrics, token_metrics


def test_make_windows_covers_long_documents() -> None:
    rows = [
        {
            "id": "doc-1",
            "tokens": ["a", "b", "c", "d", "e"],
            "token_label_ids": [0, 1, 2, 0, 0],
            "token_labels": ["O", "B-x", "I-x", "O", "O"],
        }
    ]
    windows = make_windows(rows, max_words=3, stride_words=1)
    assert [(window.start_word, window.tokens) for window in windows] == [
        (0, ["a", "b", "c"]),
        (2, ["c", "d", "e"]),
    ]


def test_load_jsonl_derives_label_ids_from_minimal_rows(tmp_path: Path) -> None:
    path = tmp_path / "minimal.jsonl"
    path.write_text(
        '{"id":"doc-1","tokens":["AFP","meldet"],"token_labels":["B-org.ent.pressagency.afp","O"]}\n',
        encoding="utf-8",
    )
    label_map = {"label2id": {"O": 0, "B-org.ent.pressagency.afp": 1}, "id2label": {"0": "O", "1": "B-org.ent.pressagency.afp"}}

    rows = load_jsonl(path, label_map=label_map)

    assert rows[0]["token_label_ids"] == [1, 0]


def test_load_jsonl_reports_unknown_minimal_label(tmp_path: Path) -> None:
    path = tmp_path / "minimal.jsonl"
    path.write_text(
        '{"id":"doc-1","tokens":["AFP"],"token_labels":["B-org.ent.pressagency.afp"]}\n',
        encoding="utf-8",
    )
    label_map = {"label2id": {"O": 0}, "id2label": {"0": "O"}}

    try:
        load_jsonl(path, label_map=label_map)
    except ValueError as exc:
        assert "token label missing from label map: B-org.ent.pressagency.afp" in str(exc)
    else:
        raise AssertionError("expected unknown label error")


def test_load_jsonl_can_ignore_unknown_eval_labels(tmp_path: Path) -> None:
    path = tmp_path / "minimal.jsonl"
    path.write_text(
        '{"id":"doc-1","tokens":["RFE"],"token_labels":["B-org.ent.radiostation.radio-free-europe"]}\n',
        encoding="utf-8",
    )
    label_map = {"label2id": {"O": 0}, "id2label": {"0": "O"}}

    rows = load_jsonl(path, label_map=label_map, unknown_label_id=-100)

    assert rows[0]["token_label_ids"] == [-100]
    assert rows[0]["token_labels"] == ["B-org.ent.radiostation.radio-free-europe"]


def test_bio_entity_metrics() -> None:
    gold = ["O", "B-org.ent.pressagency.reuters", "I-org.ent.pressagency.reuters", "O"]
    pred = ["O", "B-org.ent.pressagency.reuters", "I-org.ent.pressagency.reuters", "O"]
    assert labels_to_entities(gold) == {(1, 3, "org.ent.pressagency.reuters")}
    assert token_metrics(gold, pred)["token_non_o_f1"] == 1.0
    metrics = entity_metrics({"doc-1": gold}, {"doc-1": pred})
    assert metrics["entity_f1"] == 1.0


if __name__ == "__main__":
    test_make_windows_covers_long_documents()
    test_bio_entity_metrics()
