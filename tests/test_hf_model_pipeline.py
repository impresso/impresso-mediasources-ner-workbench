from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
HF_MODEL = ROOT / "hf_model"
sys.path.insert(0, str(HF_MODEL))

from pipeline import MediaAgenciesPipeline, NewsAgenciesPipeline, tokenize_with_offsets


ID2LABEL = {
    0: "O",
    1: "B-org.ent.pressagency.reuters",
    2: "I-org.ent.pressagency.reuters",
    3: "B-org.ent.radiostation.bbc",
    4: "I-org.ent.radiostation.bbc",
}


class FakeEncoding(dict):
    def __init__(self, tokens: list[str], label_ids: list[int], logits_by_token: list[list[float]] | None = None):
        super().__init__(
            {
                "input_ids": torch.tensor([[100 + index for index in range(len(tokens))]]),
                "attention_mask": torch.tensor([[1 for _token in tokens]]),
            }
        )
        self._word_ids = list(range(len(tokens)))
        self.label_ids = label_ids
        self.logits_by_token = logits_by_token

    def word_ids(self) -> list[int]:
        return self._word_ids


class FakeTokenizer:
    def __init__(self, label_by_token: dict[str, int], logits_by_token: dict[str, list[float]] | None = None):
        self.label_by_token = label_by_token
        self.logits_by_token = logits_by_token or {}
        self.calls: list[list[str]] = []

    def __call__(self, tokens: list[str], **_kwargs: object) -> FakeEncoding:
        self.calls.append(list(tokens))
        logits = [self.logits_by_token[token] for token in tokens] if all(token in self.logits_by_token for token in tokens) else None
        return FakeEncoding(tokens, [self.label_by_token.get(token, 0) for token in tokens], logits)


class FakeModel:
    def __init__(self, id2label: dict[int, str] | None = None):
        self.config = SimpleNamespace(
            id2label=id2label or ID2LABEL,
            annotation_tokenization="unicode-word-punctuation-v1",
            subtoken_decoding="first_subtoken_viterbi",
        )
        self.device = torch.device("cpu")

    def parameters(self):
        yield torch.nn.Parameter(torch.zeros(1))

    def to(self, device):
        self.device = torch.device(device)
        return self

    def eval(self):
        return self

    def __call__(self, **inputs):
        explicit_logits = inputs.pop("_logits", None)
        if explicit_logits is not None:
            return SimpleNamespace(logits=explicit_logits)
        label_ids = inputs.pop("_label_ids")
        logits = torch.full((1, len(label_ids), len(ID2LABEL)), -10.0)
        for token_index, label_id in enumerate(label_ids):
            logits[0, token_index, label_id] = 10.0
        return SimpleNamespace(logits=logits)


class PipelineTokenizer(FakeTokenizer):
    def __call__(self, tokens: list[str], **kwargs: object) -> FakeEncoding:
        encoding = super().__call__(tokens, **kwargs)
        encoding["_label_ids"] = encoding.label_ids
        if encoding.logits_by_token is not None:
            encoding["_logits"] = torch.tensor([encoding.logits_by_token])
        return encoding


def make_pipeline(label_by_token: dict[str, int], logits_by_token: dict[str, list[float]] | None = None, **kwargs) -> MediaAgenciesPipeline:
    return MediaAgenciesPipeline(FakeModel(), PipelineTokenizer(label_by_token, logits_by_token), **kwargs)


def test_tokenizer_matches_unicode_word_punctuation_profile() -> None:
    tokens, starts, stops = tokenize_with_offsets("Selon l'Agence France-Presse.")

    assert tokens == ["Selon", "l", "'", "Agence", "France", "-", "Presse", "."]
    assert [text for text in ("Selon l'Agence France-Presse."[start:stop] for start, stop in zip(starts, stops, strict=True))] == tokens


def test_single_string_inference_returns_exact_character_offsets() -> None:
    pipe = make_pipeline({"Reuters": 1})
    result = pipe("Reuters reported.")

    assert result["token_labels"] == ["B-org.ent.pressagency.reuters", "O", "O"]
    assert result["entities"] == [
        {
            "label": "org.ent.pressagency.reuters",
            "start": 0,
            "stop": 7,
            "surface": "Reuters",
            "confidence": pytest.approx(1.0),
        }
    ]
    assert result["text"][0:7] == "Reuters"


def test_batch_inference_and_compatibility_alias() -> None:
    assert NewsAgenciesPipeline is MediaAgenciesPipeline
    pipe = make_pipeline({"BBC": 3})

    results = pipe(["BBC said.", "No source here."])

    assert len(results) == 2
    assert results[0]["entities"][0]["label"] == "org.ent.radiostation.bbc"
    assert results[1]["entities"] == []


def test_multi_token_entity_is_decoded_with_viterbi() -> None:
    pipe = make_pipeline({"BBC": 3, "World": 4, "Service": 4})

    result = pipe("The BBC World Service reported.")

    assert result["entities"] == [
        {
            "label": "org.ent.radiostation.bbc",
            "start": 4,
            "stop": 21,
            "surface": "BBC World Service",
            "confidence": pytest.approx(1.0),
        }
    ]


def test_viterbi_entity_confidence_uses_semantic_type_probability() -> None:
    pipe = make_pipeline({}, logits_by_token={"Reuters": [0.0, 2.0, 4.0, -10.0, -10.0]})

    result = pipe("Reuters")

    assert result["token_labels"] == ["B-org.ent.pressagency.reuters"]
    assert result["token_confidences"][0] > 0.98
    assert result["entities"][0]["confidence"] == pytest.approx(result["token_confidences"][0])


def test_long_input_uses_first_covering_window_for_overlaps() -> None:
    tokenizer = PipelineTokenizer({"Reuters": 1})
    pipe = MediaAgenciesPipeline(
        FakeModel(),
        tokenizer,
        max_words_per_window=4,
        stride_words=2,
    )

    result = pipe("a b Reuters c d e")

    assert tokenizer.calls == [["a", "b", "Reuters", "c"], ["Reuters", "c", "d", "e"]]
    assert result["entities"][0]["surface"] == "Reuters"
    assert result["token_labels"] == ["O", "O", "B-org.ent.pressagency.reuters", "O", "O", "O"]


def test_pipeline_rejects_unsupported_inference_metadata() -> None:
    model = FakeModel()
    model.config.subtoken_decoding = "first_subtoken"

    with pytest.raises(ValueError, match="unsupported or missing subtoken_decoding"):
        MediaAgenciesPipeline(model, PipelineTokenizer({}))
