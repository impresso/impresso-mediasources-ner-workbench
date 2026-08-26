from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_file_list(value: str) -> list[str]:
    files = [item.strip() for item in value.split() if item.strip()]
    if not files:
        raise ValueError("release file projection is empty")
    return files


def validate_manifest_identity(manifest: dict[str, Any], *, release_id: str, version: str) -> None:
    if manifest.get("release_id") != release_id:
        raise ValueError(f"manifest release_id mismatch: expected {release_id!r}, found {manifest.get('release_id')!r}")
    if manifest.get("version") != version:
        raise ValueError(f"manifest version mismatch: expected {version!r}, found {manifest.get('version')!r}")


def validate_git_release_files(root: Path, files: list[str]) -> None:
    missing = [name for name in files if name != "manifest.json" and not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"git release projection is missing source files: {missing}")


def finalize_manifest(
    *,
    root: Path,
    release_id: str,
    version: str,
    repo_id: str,
    hf_commit_sha: str,
    hf_revision: str,
    hf_release_files: list[str],
    git_release_files: list[str],
    audit_s3_prefix: str | None = None,
) -> dict[str, Any]:
    if not SHA_RE.fullmatch(hf_commit_sha):
        raise ValueError(f"HF_COMMIT_SHA must be a 40-character git SHA, got {hf_commit_sha!r}")

    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    validate_manifest_identity(manifest, release_id=release_id, version=version)
    validate_git_release_files(root, git_release_files)

    status = manifest.get("status")
    publication = {
        "dataset_repo": repo_id,
        "hf_commit_sha": hf_commit_sha.lower(),
        "hf_revision": hf_revision,
    }

    if status == "published":
        existing_publication = manifest.get("publication")
        if existing_publication != publication:
            raise ValueError(
                "release is already published with different publication metadata: "
                f"existing={existing_publication!r} requested={publication!r}"
            )
        existing_archive = manifest.get("audit_archive") or {}
        if audit_s3_prefix and existing_archive.get("s3_prefix") not in (None, audit_s3_prefix):
            raise ValueError(
                "release already has different audit archive metadata: "
                f"existing={existing_archive.get('s3_prefix')!r} requested={audit_s3_prefix!r}"
            )
    elif status != "ready":
        raise ValueError(f"release finalization requires manifest status 'ready' or matching 'published', found {status!r}")

    manifest["status"] = "published"
    manifest["publication"] = publication
    manifest["dataset_repo"] = repo_id
    manifest["updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    manifest["files"] = {
        **dict(manifest.get("files") or {}),
        "git_release": git_release_files,
        "hf_payload_generated_by": "make publish-dataset",
        "hf_release": hf_release_files,
    }
    if audit_s3_prefix:
        manifest["audit_archive"] = {"s3_prefix": audit_s3_prefix}

    write_json(manifest_path, manifest)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record Hugging Face publication metadata in a ready dataset prerelease.")
    parser.add_argument("--dataset-source-dir", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--hf-commit-sha", required=True)
    parser.add_argument("--hf-revision", required=True)
    parser.add_argument("--hf-release-files", required=True)
    parser.add_argument("--git-release-files", required=True)
    parser.add_argument("--audit-s3-prefix")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = finalize_manifest(
        root=args.dataset_source_dir,
        release_id=args.release_id,
        version=args.version,
        repo_id=args.repo_id,
        hf_commit_sha=args.hf_commit_sha,
        hf_revision=args.hf_revision,
        hf_release_files=parse_file_list(args.hf_release_files),
        git_release_files=parse_file_list(args.git_release_files),
        audit_s3_prefix=args.audit_s3_prefix,
    )
    print(
        json.dumps(
            {
                "dataset_source_dir": str(args.dataset_source_dir),
                "publication": manifest["publication"],
                "release_id": args.release_id,
                "status": manifest["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
