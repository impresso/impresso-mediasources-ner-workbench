from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINING_SRC = ROOT / "training" / "newsagency-radiostation-modernbert-classifier" / "src"
sys.path.insert(0, str(TRAINING_SRC))

from mediaagency_modernbert.data import labels_to_entities, load_jsonl, make_windows
from mediaagency_modernbert.metrics import entity_metrics, token_metrics
from mediaagency_modernbert.train import Runtime, WindowDataset, continuation_label_ids, evaluate_rows


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

    def pad(self, features, padding=True, return_tensors="pt"):
        import torch

        return {
            "input_ids": torch.tensor([feature["input_ids"] for feature in features]),
            "attention_mask": torch.tensor([feature["attention_mask"] for feature in features]),
            "labels": torch.tensor([feature["labels"] for feature in features]),
        }

    def convert_ids_to_tokens(self, token_id):
        return ["[CLS]", "A", "##gentur", "Havas", "##x", "[SEP]"][int(token_id)]


class FakeParameter:
    @property
    def device(self):
        import torch

        return torch.device("cpu")


class FakeOutputs:
    def __init__(self, logits):
        self.logits = logits


class FakeModel:
    def parameters(self):
        return iter([FakeParameter()])

    def eval(self):
        return None

    def __call__(self, **batch):
        import torch

        logits = torch.full((batch["input_ids"].shape[0], batch["input_ids"].shape[1], 3), -5.0)
        # special tokens and first subtoken of word 0 predict O
        logits[:, :, 0] = 5.0
        # continuation subtoken of word 0 predicts B-Havas, but evaluator should discard it for word-level decoding.
        logits[:, 2, 1] = 9.0
        logits[:, 2, 0] = -5.0
        # first subtoken of word 1 predicts Havas.
        logits[:, 3, 1] = 9.0
        logits[:, 3, 0] = -5.0
        return FakeOutputs(logits)


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


def test_evaluate_rows_writes_token_and_subtoken_diagnostics(tmp_path: Path) -> None:
    import argparse
    import torch

    label_map = {
        "label2id": {"O": 0, "B-org.ent.pressagency.havas": 1, "I-org.ent.pressagency.havas": 2},
        "id2label": {"0": "O", "1": "B-org.ent.pressagency.havas", "2": "I-org.ent.pressagency.havas"},
    }
    args = argparse.Namespace(
        max_words_per_window=2,
        stride_words=0,
        max_sequence_len=512,
        eval_batch_size=1,
        train_batch_size=1,
        label_all_tokens=False,
        output_dir=str(tmp_path),
        write_prediction_diagnostics=True,
        write_token_predictions="",
        write_subtoken_predictions="",
    )
    rows = [
        {
            "id": "doc",
            "language": "fr",
            "date": "1950-01-01",
            "newspaper": "JDG",
            "tokens": ["Agentur", "Havas"],
            "token_labels": ["O", "B-org.ent.pressagency.havas"],
            "token_label_ids": [0, 1],
        }
    ]

    metrics, predictions = evaluate_rows(
        rows,
        FakeModel(),
        FakeTokenizer(),
        label_map,
        args,
        Runtime(torch=torch, Adafactor=None, AutoConfig=None, AutoModelForTokenClassification=None, AutoTokenizer=None),
        split_name="test",
        return_predictions=True,
    )

    token_tsv = (tmp_path / "test_token_predictions.tsv").read_text(encoding="utf-8")
    subtoken_tsv = (tmp_path / "test_subtoken_predictions.tsv").read_text(encoding="utf-8")
    assert predictions[0]["pred_labels"] == ["O", "B-org.ent.pressagency.havas"]
    assert metrics["windows"] == 1
    assert "Agentur\tO\tO\t" in token_tsv
    assert "raw_first_subtoken_pred_label\tpred_label" in token_tsv.splitlines()[0]
    assert "absolute_word_index\tword\tsubtoken_index" in subtoken_tsv.splitlines()[0]
    assert "0\tAgentur\t2\t##gentur\t0\t0\t-100\tIGNORED\tB-org.ent.pressagency.havas" in subtoken_tsv
    assert "source_window_index" in token_tsv.splitlines()[0]


def test_token_diagnostics_distinguish_raw_first_subtoken_from_decoded_label(tmp_path: Path) -> None:
    import argparse
    import torch

    class OneSubtokenEncoding(dict):
        def __init__(self, token_count: int):
            super().__init__({"input_ids": list(range(token_count)), "attention_mask": [1] * token_count})
            self._word_ids = list(range(token_count))

        def word_ids(self) -> list[int]:
            return self._word_ids

    class OneSubtokenTokenizer:
        def __call__(self, tokens, **_kwargs):
            return OneSubtokenEncoding(len(tokens))

        def pad(self, features, padding=True, return_tensors="pt"):
            return {
                "input_ids": torch.tensor([feature["input_ids"] for feature in features]),
                "attention_mask": torch.tensor([feature["attention_mask"] for feature in features]),
                "labels": torch.tensor([feature["labels"] for feature in features]),
            }

        def convert_ids_to_tokens(self, token_id):
            return f"tok-{token_id}"

    class ViterbiFixtureModel:
        def parameters(self):
            return iter([FakeParameter()])

        def eval(self):
            return None

        def __call__(self, **batch):
            logits = torch.full((1, 4, 5), -10.0)
            # O, B-AFP, I-AFP, B-Wolff, I-Wolff. I-Wolff is locally best at
            # Presse but illegal after I-AFP, so Viterbi must choose B-Wolff.
            logits[0, 0, 1] = 10.0
            logits[0, 1, 2] = 10.0
            logits[0, 2, 2] = 10.0
            logits[0, 3, 4] = 10.0
            logits[0, 3, 3] = 9.0
            return FakeOutputs(logits)

    label_map = {
        "label2id": {
            "O": 0,
            "B-org.ent.pressagency.afp": 1,
            "I-org.ent.pressagency.afp": 2,
            "B-org.ent.pressagency.wolff": 3,
            "I-org.ent.pressagency.wolff": 4,
        },
        "id2label": {
            "0": "O",
            "1": "B-org.ent.pressagency.afp",
            "2": "I-org.ent.pressagency.afp",
            "3": "B-org.ent.pressagency.wolff",
            "4": "I-org.ent.pressagency.wolff",
        },
    }
    args = argparse.Namespace(
        max_words_per_window=4,
        stride_words=0,
        max_sequence_len=512,
        eval_batch_size=1,
        train_batch_size=1,
        label_all_tokens=False,
        output_dir=str(tmp_path),
        write_prediction_diagnostics=True,
        write_token_predictions="",
        write_subtoken_predictions="",
        decoder="first_subtoken_viterbi",
        compare_decoders=False,
    )
    rows = [
        {
            "id": "doc",
            "tokens": ["Agence", "France", "-", "Presse"],
            "token_labels": ["O", "O", "O", "O"],
            "token_label_ids": [0, 0, 0, 0],
        }
    ]

    _metrics, predictions = evaluate_rows(
        rows,
        ViterbiFixtureModel(),
        OneSubtokenTokenizer(),
        label_map,
        args,
        Runtime(torch=torch, Adafactor=None, AutoConfig=None, AutoModelForTokenClassification=None, AutoTokenizer=None),
        split_name="test",
        return_predictions=True,
    )

    token_tsv = (tmp_path / "test_token_predictions.tsv").read_text(encoding="utf-8")
    assert predictions[0]["pred_labels"][-1] == "B-org.ent.pressagency.wolff"
    assert "\tPresse\tO\tI-org.ent.pressagency.wolff\tB-org.ent.pressagency.wolff\t" in token_tsv


def test_evaluate_rows_uses_model_label_map_for_logits_and_dataset_map_for_gold(tmp_path: Path) -> None:
    import argparse
    import torch

    dataset_label_map = {
        "label2id": {"O": 0, "B-org.ent.pressagency.havas": 7, "I-org.ent.pressagency.havas": 8},
        "id2label": {"0": "O", "7": "B-org.ent.pressagency.havas", "8": "I-org.ent.pressagency.havas"},
    }
    model_label_map = {
        "label2id": {"O": 0, "B-org.ent.pressagency.havas": 1, "I-org.ent.pressagency.havas": 2},
        "id2label": {"0": "O", "1": "B-org.ent.pressagency.havas", "2": "I-org.ent.pressagency.havas"},
    }
    args = argparse.Namespace(
        max_words_per_window=2,
        stride_words=0,
        max_sequence_len=512,
        eval_batch_size=1,
        train_batch_size=1,
        label_all_tokens=False,
        output_dir=str(tmp_path),
        write_prediction_diagnostics=True,
        write_token_predictions="",
        write_subtoken_predictions="",
        decoder="first_subtoken",
        compare_decoders=False,
    )
    rows = [
        {
            "id": "doc",
            "tokens": ["Agentur", "Havas"],
            "token_labels": ["O", "B-org.ent.pressagency.havas"],
            "token_label_ids": [0, 7],
        }
    ]

    _metrics, predictions = evaluate_rows(
        rows,
        FakeModel(),
        FakeTokenizer(),
        dataset_label_map,
        args,
        Runtime(torch=torch, Adafactor=None, AutoConfig=None, AutoModelForTokenClassification=None, AutoTokenizer=None),
        split_name="test",
        return_predictions=True,
        model_label_map=model_label_map,
    )

    subtoken_tsv = (tmp_path / "test_subtoken_predictions.tsv").read_text(encoding="utf-8")
    assert predictions[0]["pred_labels"] == ["O", "B-org.ent.pressagency.havas"]
    assert "\t7\tB-org.ent.pressagency.havas\tB-org.ent.pressagency.havas" in subtoken_tsv


def test_evaluate_rows_can_compare_decoders(tmp_path: Path) -> None:
    import argparse
    import torch

    label_map = {
        "label2id": {"O": 0, "B-org.ent.pressagency.havas": 1, "I-org.ent.pressagency.havas": 2},
        "id2label": {"0": "O", "1": "B-org.ent.pressagency.havas", "2": "I-org.ent.pressagency.havas"},
    }
    args = argparse.Namespace(
        max_words_per_window=2,
        stride_words=0,
        max_sequence_len=512,
        eval_batch_size=1,
        train_batch_size=1,
        label_all_tokens=False,
        output_dir=str(tmp_path),
        write_prediction_diagnostics=False,
        write_token_predictions="",
        write_subtoken_predictions="",
        decoder="first_subtoken_viterbi",
        compare_decoders=True,
    )
    rows = [
        {
            "id": "doc",
            "language": "fr",
            "date": "1950-01-01",
            "newspaper": "JDG",
            "tokens": ["Agentur", "Havas"],
            "token_labels": ["O", "B-org.ent.pressagency.havas"],
            "token_label_ids": [0, 1],
        }
    ]

    metrics, predictions = evaluate_rows(
        rows,
        FakeModel(),
        FakeTokenizer(),
        label_map,
        args,
        Runtime(torch=torch, Adafactor=None, AutoConfig=None, AutoModelForTokenClassification=None, AutoTokenizer=None),
        split_name="test",
        return_predictions=True,
    )

    comparison_tsv = (tmp_path / "test_decoder_comparison.tsv").read_text(encoding="utf-8")
    assert metrics["decoder"] == "first_subtoken_viterbi"
    assert set(metrics["decoder_comparison"]) == {
        "first_subtoken",
        "first_subtoken_viterbi",
        "all_subtoken",
        "all_subtoken_viterbi",
    }
    assert predictions[0]["pred_labels"] == ["O", "B-org.ent.pressagency.havas"]
    assert "first_subtoken\tfirst_subtoken_viterbi\tall_subtoken\tall_subtoken_viterbi" in comparison_tsv.splitlines()[0]


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
