from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from lib.score_newsagency_snippets import validate_model_inference_metadata
from lib.stamp_model_inference_metadata import dataset_profile, stamp_config


ROOT = Path(__file__).resolve().parents[1]
TRAINING_SRC = ROOT / "training" / "newsagency-radiostation-modernbert-classifier" / "src"
sys.path.insert(0, str(TRAINING_SRC))

from mediaagency_modernbert.train import configure_inference_metadata


def test_training_config_records_mode_b_and_default_viterbi_decoding() -> None:
    model = SimpleNamespace(config=SimpleNamespace())

    configure_inference_metadata(
        model,
        [{"tokenization": "unicode-word-punctuation-v1"}],
        label_all_tokens=True,
    )

    assert model.config.annotation_tokenization == "unicode-word-punctuation-v1"
    assert model.config.label_all_tokens is True
    assert model.config.subtoken_labeling == "all_subtokens_b_to_i"
    assert model.config.subtoken_decoding == "first_subtoken_viterbi"


def test_stamp_config_supports_already_running_mode_a_training(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"model_type":"modernbert"}\n', encoding="utf-8")

    result = stamp_config(config_path, profile="unicode-word-punctuation-v1", label_all_tokens=False)
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert result["subtoken_labeling"] == "first_subtoken_only"
    assert config["label_all_tokens"] is False
    assert config["subtoken_decoding"] == "first_subtoken_viterbi"


def test_dataset_profile_requires_one_declared_profile(tmp_path: Path) -> None:
    dataset = tmp_path / "train.jsonl"
    dataset.write_text('{"tokenization":"unicode-word-punctuation-v1"}\n', encoding="utf-8")

    assert dataset_profile(dataset) == "unicode-word-punctuation-v1"


def test_inference_rejects_missing_or_unknown_decoding_policy() -> None:
    with pytest.raises(ValueError, match="lacks inference metadata"):
        validate_model_inference_metadata(SimpleNamespace(), "checkpoint")

    config = SimpleNamespace(
        annotation_tokenization="unicode-word-punctuation-v1",
        label_all_tokens=False,
        subtoken_labeling="first_subtoken_only",
        subtoken_decoding="mean_pool",
    )
    with pytest.raises(ValueError, match="unsupported subtoken decoding"):
        validate_model_inference_metadata(config, "checkpoint")
