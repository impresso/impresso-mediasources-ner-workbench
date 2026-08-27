from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .env import load_dotenv_if_available


DEFAULT_TEXTS = [
    "Reuters reported from London.",
    "Selon l'Agence France-Presse, Radio Prague a confirmé la nouvelle.",
    "This sentence contains no cited media source.",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small inference smoke test for the HF media-sources pipeline.")
    parser.add_argument("--model", required=True, help="Local checkpoint directory or Hugging Face model revision.")
    parser.add_argument("--revision", default=None, help="Optional Hugging Face revision for --model.")
    parser.add_argument("--text", action="append", default=[], help="Text to infer. Can be supplied multiple times.")
    parser.add_argument("--pipeline-dir", default="hf_model", help="Directory containing pipeline.py and decoding.py.")
    parser.add_argument("--device", default=None, help="Torch device, e.g. cpu, mps, cuda:0. Defaults to pipeline CPU.")
    parser.add_argument("--max-words-per-window", type=int, default=256)
    parser.add_argument("--stride-words", type=int, default=32)
    parser.add_argument("--max-sequence-len", type=int, default=512)
    return parser.parse_args(argv)


def import_runtime():
    load_dotenv_if_available()
    try:
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError as exc:
        raise SystemExit("model inference smoke test requires transformers and torch") from exc
    return AutoModelForTokenClassification, AutoTokenizer


def import_pipeline(pipeline_dir: Path):
    sys.path.insert(0, str(pipeline_dir.resolve()))
    try:
        from pipeline import MediaAgenciesPipeline
    except ImportError as exc:
        raise SystemExit(f"cannot import MediaAgenciesPipeline from {pipeline_dir}") from exc
    return MediaAgenciesPipeline


def resolve_model_source(model: str, *, revision: str | None = None) -> tuple[str, dict[str, str]]:
    path = Path(model).expanduser()
    if path.exists():
        return str(path.resolve()), {}
    return model, {"revision": revision} if revision else {}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    AutoModelForTokenClassification, AutoTokenizer = import_runtime()
    MediaAgenciesPipeline = import_pipeline(Path(args.pipeline_dir))

    model_source, load_kwargs = resolve_model_source(args.model, revision=args.revision)
    tokenizer = AutoTokenizer.from_pretrained(model_source, **load_kwargs)
    model = AutoModelForTokenClassification.from_pretrained(model_source, **load_kwargs)
    pipeline = MediaAgenciesPipeline(
        model,
        tokenizer,
        device=args.device,
        max_sequence_len=args.max_sequence_len,
        max_words_per_window=args.max_words_per_window,
        stride_words=args.stride_words,
    )
    texts = args.text or DEFAULT_TEXTS
    results = pipeline(texts)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    for result in results:
        text = result["text"]
        for entity in result["entities"]:
            if text[int(entity["start"]) : int(entity["stop"])] != entity["surface"]:
                raise SystemExit(f"entity offset/surface mismatch: {entity}")
    print(json.dumps({"model": model_source, "texts": len(texts), "status": "ok"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
