from __future__ import annotations

import json
from pathlib import Path

from lib.push_model_to_hub import copy_payload


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_copy_payload_uses_selected_model_and_run_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    selected_model = run_dir / "best"
    out_dir = tmp_path / "payload"
    card = tmp_path / "README.md"
    requirements = tmp_path / "requirements.txt"
    provenance = tmp_path / "model_provenance.json"

    write(selected_model / "config.json", json.dumps({"model_type": "modernbert"}))
    for name in ("model.safetensors", "tokenizer.json", "tokenizer_config.json"):
        write(selected_model / name, f"selected {name}")
    write(run_dir / "label_map.json", json.dumps({"label2id": {"O": 0}}))
    write(run_dir / "training_args.json", json.dumps({"decoder": "first_subtoken_viterbi"}))
    write(run_dir / "training_start_report.json", json.dumps({"base_model": "base"}))
    write(run_dir / "best_validation_metrics.json", json.dumps({"entity_f1": 0.9285}))
    write(run_dir / "eval" / "validation_metrics.json", json.dumps({"entity_f1": 0.9285}))
    write(run_dir / "eval" / "test_metrics.json", json.dumps({"entity_f1": 0.8981}))
    write(card, "# Model Card\n")
    write(requirements, "transformers\n")
    write(provenance, json.dumps({"model": {"revision": "v2.0.0"}}))

    copy_payload(selected_model, run_dir, card, requirements, provenance, out_dir, include_eval_metrics=True)

    config = json.loads((out_dir / "config.json").read_text(encoding="utf-8"))
    assert config["custom_pipelines"]["token-classification"] == {
        "impl": "pipeline.MediaAgenciesPipeline",
        "pt": ["AutoModelForTokenClassification"],
    }
    assert json.loads((out_dir / "label_map.json").read_text(encoding="utf-8")) == {"label2id": {"O": 0}}
    assert json.loads((out_dir / "model_provenance.json").read_text(encoding="utf-8")) == {
        "model": {"revision": "v2.0.0"}
    }
    assert json.loads((out_dir / "eval" / "test_metrics.json").read_text(encoding="utf-8")) == {
        "entity_f1": 0.8981
    }
    assert (out_dir / "pipeline.py").is_file()
    assert (out_dir / "decoding.py").is_file()
