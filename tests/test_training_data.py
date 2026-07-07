from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINING_SRC = ROOT / "training" / "newsagency-radiostation-modernbert-classifier" / "src"
sys.path.insert(0, str(TRAINING_SRC))

from mediaagency_modernbert.data import labels_to_entities, load_jsonl, make_windows
from mediaagency_modernbert.metrics import entity_metrics, token_metrics
from mediaagency_modernbert.train import WindowDataset, continuation_label_ids


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


class FakeEncoding(dict):
    def __init__(self, word_ids: list[int | None]):
        super().__init__({"input_ids": list(range(len(word_ids))), "attention_mask": [1] * len(word_ids)})
        self._word_ids = word_ids

    def word_ids(self) -> list[int | None]:
        return self._word_ids


class FakeTokenizer:
    def __call__(self, *_args, **_kwargs):
        return FakeEncoding([None, 0, 0, 1, 1, None])


def test_window_dataset_mode_a_ignores_continuation_subtokens() -> None:
    windows = make_windows(
        [{"id": "doc", "tokens": ["Agence", "Havas"], "token_label_ids": [1, 0]}],
        max_words=2,
        stride_words=0,
    )

    encoded = WindowDataset(windows, FakeTokenizer(), 512)[0]

    assert encoded["labels"] == [-100, 1, -100, 0, -100, -100]


def test_mode_a_does_not_require_unobserved_i_label() -> None:
    label_map = {
        "label2id": {"O": 0, "B-org.ent.pressagency.keystone": 1},
        "id2label": {"0": "O", "1": "B-org.ent.pressagency.keystone"},
    }

    # Mode A does not construct or use a continuation map.
    assert label_map["label2id"]["B-org.ent.pressagency.keystone"] == 1


def test_window_dataset_mode_b_labels_continuations_with_b_to_i() -> None:
    label_map = {
        "label2id": {"O": 0, "B-org.ent.pressagency.havas": 1, "I-org.ent.pressagency.havas": 2},
        "id2label": {"0": "O", "1": "B-org.ent.pressagency.havas", "2": "I-org.ent.pressagency.havas"},
    }
    windows = make_windows(
        [{"id": "doc", "tokens": ["Agence", "Havas"], "token_label_ids": [1, 0]}],
        max_words=2,
        stride_words=0,
    )

    encoded = WindowDataset(
        windows,
        FakeTokenizer(),
        512,
        label_all_tokens=True,
        continuation_label_ids=continuation_label_ids(label_map),
    )[0]

    assert encoded["labels"] == [-100, 1, 2, 0, 0, -100]


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
