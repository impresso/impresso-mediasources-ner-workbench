from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from .env import load_dotenv_if_available


def import_runtime():
    load_dotenv_if_available()
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise SystemExit('Hugging Face publishing requires huggingface-hub. Install with: python -m pip install -e ".[hf]"') from exc
    return HfApi


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push continued-MLM model payload to Hugging Face.")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--model-dir", required=True, help="Directory containing the final model payload.")
    parser.add_argument("--card", required=True, help="README.md source model card.")
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def copy_payload(model_dir: Path, card: Path, out_dir: Path) -> None:
    for path in model_dir.iterdir():
        target = out_dir / path.name
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    shutil.copy2(card, out_dir / "README.md")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    model_dir = Path(args.model_dir)
    card = Path(args.card)
    if not model_dir.is_dir():
        raise SystemExit(f"model directory does not exist: {model_dir}")
    if not card.is_file():
        raise SystemExit(f"model card does not exist: {card}")

    if args.dry_run:
        print(f"dry-run: would push {model_dir} with card {card} to {args.repo_id}")
        return 0

    HfApi = import_runtime()
    api = HfApi()
    api.create_repo(repo_id=args.repo_id, repo_type="model", private=args.private, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mlm-model-upload-") as tmp:
        upload_dir = Path(tmp)
        copy_payload(model_dir, card, upload_dir)
        api.upload_folder(
            repo_id=args.repo_id,
            repo_type="model",
            folder_path=str(upload_dir),
            commit_message="Upload continued MLM checkpoint",
        )
    print(f"pushed model to https://huggingface.co/{args.repo_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
