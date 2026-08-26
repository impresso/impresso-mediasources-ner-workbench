from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def parse_file_list(value: str) -> list[str]:
    files = [item.strip() for item in value.split() if item.strip()]
    if not files:
        raise ValueError("release file projection is empty")
    return files


def copy_projection(*, source_dir: Path, release_dir: Path, release_files: list[str]) -> list[str]:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"source directory does not exist: {source_dir}")
    if release_dir.exists():
        raise FileExistsError(
            f"release directory already exists: {release_dir}; release IDs are immutable, create a patch release instead"
        )

    manifest = read_json(source_dir / "manifest.json")
    if manifest.get("status") != "ready":
        raise ValueError(f"release promotion requires manifest status 'ready', found {manifest.get('status')!r}")

    missing = [name for name in release_files if not (source_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"release projection is missing source files: {missing}")

    release_dir.mkdir(parents=True)
    copied: list[str] = []
    try:
        for name in release_files:
            source = source_dir / name
            target = release_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(name)
    except Exception:
        shutil.rmtree(release_dir, ignore_errors=True)
        raise
    return copied


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project a ready prerelease into an immutable git release snapshot.")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--release-files", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    release_files = parse_file_list(args.release_files)
    manifest = read_json(args.source_dir / "manifest.json")
    if manifest.get("status") != "ready":
        raise SystemExit(f"release promotion requires manifest status 'ready', found {manifest.get('status')!r}")
    missing = [name for name in release_files if not (args.source_dir / name).is_file()]
    if missing:
        raise SystemExit(f"release projection is missing source files: {missing}")
    if args.release_dir.exists():
        raise SystemExit(
            f"release directory already exists: {args.release_dir}; release IDs are immutable, create a patch release instead"
        )
    copied = release_files if args.dry_run else copy_projection(
        source_dir=args.source_dir,
        release_dir=args.release_dir,
        release_files=release_files,
    )
    print(
        json.dumps(
            {
                "copied": copied,
                "dry_run": bool(args.dry_run),
                "release_dir": str(args.release_dir),
                "source_dir": str(args.source_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
