from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .dataset_statistics import SPLITS, collect_statistics, load_jsonl


DEFAULT_RELEASE_FILES = (
    "train.jsonl",
    "validation.jsonl",
    "test.jsonl",
    "label_map.json",
    "dataset_summary.json",
    "manifest.json",
    "DATASET_STATISTICS.md",
    "DATASET_QUALITY.md",
    "SUBTOKEN_STRATEGY_REPORT.md",
    "TOKENIZATION_MIGRATION.md",
    "curation_summary.json",
    "curation_changes.jsonl",
    "curation_changes_tags.tsv",
    "tokenization_migration_summary.json",
    "tokenization_migration_changes.jsonl",
    "tsv/train.tsv",
    "tsv/validation.tsv",
    "tsv/test.tsv",
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def remove_ds_store(root: Path) -> list[str]:
    removed: list[str] = []
    for path in sorted(root.rglob(".DS_Store")):
        if path.is_file():
            removed.append(str(path.relative_to(root)))
            path.unlink()
    return removed


def entity_label_counts(rows_by_split: dict[str, list[dict[str, Any]]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for rows in rows_by_split.values():
        for row in rows:
            counts.update(str(entity.get("label") or "") for entity in row.get("entities") or [])
    counts.pop("", None)
    return counts


def existing_release_files(root: Path) -> list[str]:
    return [name for name in DEFAULT_RELEASE_FILES if (root / name).is_file()]


def build_dataset_summary(root: Path, *, repo_id: str, release: str) -> dict[str, Any]:
    rows_by_split = {split: load_jsonl(root / f"{split}.jsonl") for split in SPLITS}
    stats = collect_statistics(rows_by_split)
    label_map = read_json(root / "label_map.json")
    label_counts = entity_label_counts(rows_by_split)

    return {
        "release": release,
        "repo_id": repo_id,
        "format": "jsonl",
        "splits": {split: int(stats["splits"][split]["documents"]) for split in SPLITS},
        "languages_by_split": stats["languages"],
        "tokens_by_split": {split: int(stats["splits"][split]["tokens"]) for split in SPLITS},
        "entities_by_split": {split: int(stats["splits"][split]["mentions"]) for split in SPLITS},
        "entity_labels": dict(sorted(label_counts.items())),
        "entity_families_by_split": stats["families"],
        "label_count": len(label_map.get("label2id") or {}),
        "files": existing_release_files(root),
        "public_row_fields": [
            "schema_version",
            "tokenization",
            "id",
            "document_id",
            "split",
            "language",
            "newspaper",
            "date",
            "year",
            "text",
            "tokens",
            "token_start_offsets",
            "token_end_offsets",
            "token_labels",
            "entities",
            "audit_marks",
            "quality_flags",
            "legacy",
        ],
        "public_entity_fields": [
            "label",
            "entity_family",
            "token_start",
            "token_stop",
            "start",
            "stop",
            "surface",
            "wikidata_url",
            "ocr_correction",
        ],
        "duplicate_document_ids": stats["duplicate_document_ids"],
    }


def manifest_summary(dataset_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "documents_by_split": dataset_summary["splits"],
        "entities_by_split": dataset_summary["entities_by_split"],
        "languages_by_split": dataset_summary["languages_by_split"],
        "label_count": dataset_summary["label_count"],
    }


def build_manifest(
    root: Path,
    *,
    release_id: str,
    version: str,
    status: str,
    repo_id: str,
    dataset_summary: dict[str, Any],
    base: dict[str, Any],
) -> dict[str, Any]:
    manifest = dict(base)
    manifest["release_id"] = release_id
    manifest["version"] = version
    manifest["status"] = status
    manifest["dataset_repo"] = repo_id
    manifest["updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    manifest["summary"] = manifest_summary(dataset_summary)
    manifest["files"] = {
        "release_snapshot": dataset_summary["files"],
        "hf_payload_generated_by": "make publish-dataset",
    }
    manifest["created_from"] = {
        **dict(manifest.get("created_from") or {}),
        "prerelease_path": str(root),
        "public_projection": "lib.publish_dataset.public_row",
    }
    manifest["notes"] = (
        "Committed dataset release-candidate snapshot. The JSONL files use the compact public training schema. "
        "Run make publish-dataset to stage the Hugging Face payload with data/train.jsonl, "
        "data/validation.jsonl, and data/test.jsonl."
    )
    return manifest


def validate_release_files(root: Path, *, max_git_file_mb: int) -> list[str]:
    errors: list[str] = []
    for split in SPLITS:
        path = root / f"{split}.jsonl"
        if not path.is_file():
            errors.append(f"missing split file: {path}")
    for name in ("label_map.json", "dataset_summary.json", "manifest.json"):
        if not (root / name).is_file():
            errors.append(f"missing release file: {root / name}")
    max_bytes = max_git_file_mb * 1024 * 1024
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.stat().st_size > max_bytes:
            errors.append(f"file exceeds {max_git_file_mb} MiB: {path} ({path.stat().st_size} bytes)")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh release metadata for the configured dataset prerelease snapshot.")
    parser.add_argument("--dataset-source-dir", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--status", default="prerelease", choices=("prerelease", "ready", "published"))
    parser.add_argument("--remove-ds-store", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-git-file-mb", type=int, default=50)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.dataset_source_dir
    if not root.is_dir():
        raise SystemExit(f"dataset source directory does not exist: {root}")

    removed = remove_ds_store(root) if args.remove_ds_store else []
    dataset_summary = build_dataset_summary(root, repo_id=args.repo_id, release=args.version)
    write_json(root / "dataset_summary.json", dataset_summary)

    manifest = build_manifest(
        root,
        release_id=args.release_id,
        version=args.version,
        status=args.status,
        repo_id=args.repo_id,
        dataset_summary=dataset_summary,
        base=read_json(root / "manifest.json"),
    )
    write_json(root / "manifest.json", manifest)

    errors = validate_release_files(root, max_git_file_mb=args.max_git_file_mb)
    result = {
        "dataset_source_dir": str(root),
        "dataset_summary": str(root / "dataset_summary.json"),
        "errors": errors,
        "manifest": str(root / "manifest.json"),
        "release_id": args.release_id,
        "removed_ds_store": removed,
        "status": args.status,
        "summary": manifest["summary"],
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
