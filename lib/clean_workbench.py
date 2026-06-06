from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


TOP_LEVEL_GENERATED_DIRS = (
    "*.d",
    ".cache",
    ".hf",
    "data/mlm",
    "models",
    "outputs",
    "results",
)
LOCAL_DATA_DIRS = (
    "data/candidates",
    "data/curated",
    "data/testset",
)
PRESERVE_FILE_NAMES = {".gitkeep"}


@dataclass(frozen=True)
class CleanItem:
    path: Path
    kind: str


def resolve_repo_root(value: str | Path) -> Path:
    return Path(value).resolve()


def ensure_inside_repo(repo_root: Path, path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"refusing to clean path outside repository: {path}") from exc


def top_level_generated_items(repo_root: Path) -> list[CleanItem]:
    items: list[CleanItem] = []
    for pattern in TOP_LEVEL_GENERATED_DIRS:
        for path in sorted(repo_root.glob(pattern)):
            ensure_inside_repo(repo_root, path)
            if path.is_dir():
                items.append(CleanItem(path=path, kind="generated-root"))
    return dedupe_items(items)


def local_data_items(repo_root: Path) -> list[CleanItem]:
    items: list[CleanItem] = []
    for relative in LOCAL_DATA_DIRS:
        root = repo_root / relative
        ensure_inside_repo(repo_root, root)
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            ensure_inside_repo(repo_root, child)
            if child.name in PRESERVE_FILE_NAMES:
                continue
            items.append(CleanItem(path=child, kind="local-data"))
    return dedupe_items(items)


def dedupe_items(items: list[CleanItem]) -> list[CleanItem]:
    seen: set[Path] = set()
    out: list[CleanItem] = []
    for item in items:
        resolved = item.path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(item)
    return out


def collect_clean_items(repo_root: Path) -> list[CleanItem]:
    return dedupe_items([*top_level_generated_items(repo_root), *local_data_items(repo_root)])


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def clean(repo_root: Path, *, dry_run: bool) -> dict[str, object]:
    repo_root = resolve_repo_root(repo_root)
    items = collect_clean_items(repo_root)
    removed: list[dict[str, str]] = []
    for item in items:
        relative = item.path.resolve().relative_to(repo_root)
        removed.append({"path": str(relative), "kind": item.kind})
        if not dry_run:
            remove_path(item.path)
    return {"dry_run": dry_run, "count": len(removed), "items": removed}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove local generated workbench data.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = clean(Path(args.repo_root), dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
