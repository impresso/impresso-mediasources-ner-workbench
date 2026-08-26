from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from .env import load_dotenv_if_available


REQUIRED_MODEL_FILES = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")


def import_runtime():
    load_dotenv_if_available()
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise SystemExit('Hugging Face publishing requires huggingface-hub. Install with: python -m pip install -e ".[hf]"') from exc
    return HfApi


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push model payload to Hugging Face.")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", required=True)
    parser.add_argument("--card", default="hf_model/README.md")
    parser.add_argument("--requirements", default="hf_model/requirements.txt")
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--include-eval-metrics", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise SystemExit(f"{description} does not exist: {path}")


def copy_if_exists(source: Path, target: Path) -> None:
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def copy_hf_model_sources(out_dir: Path) -> None:
    source_dir = Path("hf_model")
    for name in ("pipeline.py", "decoding.py"):
        copy_if_exists(source_dir / name, out_dir / name)


def copy_payload(model_dir: Path, card: Path, requirements: Path, out_dir: Path, *, include_eval_metrics: bool) -> None:
    for name in REQUIRED_MODEL_FILES:
        source = model_dir / name
        require_file(source, f"required model file {name}")
        shutil.copy2(source, out_dir / name)

    shutil.copy2(card, out_dir / "README.md")
    copy_if_exists(requirements, out_dir / "requirements.txt")
    copy_hf_model_sources(out_dir)

    parent = model_dir.parent
    for name in ("label_map.json", "training_args.json", "training_start_report.json", "best_validation_metrics.json"):
        copy_if_exists(parent / name, out_dir / name)

    if include_eval_metrics:
        for name in ("validation_metrics.json", "test_metrics.json"):
            copy_if_exists(model_dir / "eval" / name, out_dir / "eval" / name)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    model_dir = Path(args.model)
    card = Path(args.card)
    requirements = Path(args.requirements)
    if not model_dir.is_dir():
        raise SystemExit(f"model directory does not exist: {model_dir}")
    require_file(card, "model card")
    if args.dry_run:
        print(f"dry-run: would push model payload {args.model} with card {args.card} to {args.repo_id}")
        return 0

    HfApi = import_runtime()
    api = HfApi()
    api.create_repo(repo_id=args.repo_id, repo_type="model", private=args.private, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="media-source-ner-upload-") as tmp:
        upload_dir = Path(tmp)
        copy_payload(model_dir, card, requirements, upload_dir, include_eval_metrics=args.include_eval_metrics)
        api.upload_folder(
            repo_id=args.repo_id,
            repo_type="model",
            folder_path=str(upload_dir),
            commit_message="Upload fine-tuned media sources NER model",
        )
    print(f"pushed model to https://huggingface.co/{args.repo_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
