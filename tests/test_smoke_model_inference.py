from __future__ import annotations

from pathlib import Path

from lib.smoke_model_inference import resolve_model_source


def test_local_model_source_is_resolved_without_revision(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    source, kwargs = resolve_model_source(str(model_dir), revision="v2.0.0")

    assert source == str(model_dir.resolve())
    assert kwargs == {}


def test_hf_model_source_preserves_revision() -> None:
    source, kwargs = resolve_model_source(
        "impresso-project/mmbert-impresso-mediasources-ner",
        revision="v2.0.0",
    )

    assert source == "impresso-project/mmbert-impresso-mediasources-ner"
    assert kwargs == {"revision": "v2.0.0"}
