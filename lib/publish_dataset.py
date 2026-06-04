from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from huggingface_hub import CommitOperationAdd, HfApi

from .env import load_dotenv_if_available


SPLITS = ("train", "validation", "test")
PRIMARY_FILES = tuple(f"{split}.jsonl" for split in SPLITS) + ("label_map.json",)
OPTIONAL_AUDIT_FILES = ("curation_summary.json", "curation_changes.jsonl", "curation_changes_tags.tsv")
PUBLIC_ROW_FIELDS = (
    "schema_version",
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
    "token_label_ids",
    "entities",
    "quality_flags",
)
PUBLIC_ENTITY_FIELDS = (
    "entity_id",
    "label",
    "entity_family",
    "token_start",
    "token_stop",
    "start",
    "stop",
    "surface",
    "normalized_surface",
    "nel",
    "wikidata_url",
    "has_ocr_correction",
    "max_ocr_levenshtein",
)
LEGACY_TRACE_FIELDS = ("source_format", "source_file", "news_agency_as_source")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def public_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {field: entity[field] for field in PUBLIC_ENTITY_FIELDS if field in entity}


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {field: row[field] for field in PUBLIC_ROW_FIELDS if field in row and field != "entities"}
    out["entities"] = [public_entity(entity) for entity in row.get("entities", [])]
    legacy = {field: row[field] for field in LEGACY_TRACE_FIELDS if row.get(field) not in (None, "", [])}
    if legacy:
        out["legacy"] = legacy
    return out


def prepare_dataset_repo(
    *,
    input_dir: Path,
    output_dir: Path,
    card_path: Path,
    repo_id: str,
    include_audit: bool,
    allowed_labels: set[str] | None = None,
) -> dict[str, Any]:
    for file_name in PRIMARY_FILES:
        if not (input_dir / file_name).is_file():
            raise FileNotFoundError(input_dir / file_name)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "data").mkdir(parents=True)

    for split in SPLITS:
        rows = load_jsonl(input_dir / f"{split}.jsonl")
        write_jsonl(output_dir / "data" / f"{split}.jsonl", (public_row(row) for row in rows))
    copy_file(input_dir / "label_map.json", output_dir / "label_map.json")
    copy_file(card_path, output_dir / "README.md")

    copied_audit = []
    if include_audit:
        audit_dir = output_dir / "audit"
        for file_name in OPTIONAL_AUDIT_FILES:
            source = input_dir / file_name
            if source.is_file():
                copy_file(source, audit_dir / file_name)
                copied_audit.append(f"audit/{file_name}")

    summary = dataset_summary(dataset_dir=output_dir, repo_id=repo_id, audit_files=copied_audit)
    if allowed_labels is not None:
        unknown = sorted(set(summary["entity_labels"]) - allowed_labels)
        if unknown:
            raise ValueError(f"dataset contains labels not present in canonical metadata: {unknown}")
    write_json(output_dir / "dataset_summary.json", summary)
    return summary


def dataset_summary(*, dataset_dir: Path, repo_id: str, audit_files: list[str]) -> dict[str, Any]:
    label_map = json.loads((dataset_dir / "label_map.json").read_text(encoding="utf-8"))
    rows_by_split = {split: load_jsonl(dataset_dir / "data" / f"{split}.jsonl") for split in SPLITS}
    language_counts: dict[str, dict[str, int]] = {}
    token_counts: dict[str, int] = {}
    entity_counts: dict[str, int] = {}
    label_counts: Counter[str] = Counter()

    for split, rows in rows_by_split.items():
        language_counts[split] = dict(sorted(Counter(str(row.get("language", "")) for row in rows).items()))
        token_counts[split] = sum(len(row["tokens"]) for row in rows)
        entity_counts[split] = sum(len(row.get("entities", [])) for row in rows)
        for row in rows:
            label_counts.update(entity["label"] for entity in row.get("entities", []))

    return {
        "repo_id": repo_id,
        "format": "jsonl",
        "splits": {split: len(rows) for split, rows in rows_by_split.items()},
        "languages_by_split": language_counts,
        "tokens_by_split": token_counts,
        "entities_by_split": entity_counts,
        "entity_labels": dict(sorted(label_counts.items())),
        "label_count": len(label_map["label2id"]),
        "files": [f"data/{split}.jsonl" for split in SPLITS] + ["label_map.json", "dataset_summary.json", *audit_files],
        "public_row_fields": list(PUBLIC_ROW_FIELDS) + ["legacy"],
        "public_entity_fields": list(PUBLIC_ENTITY_FIELDS),
        "legacy_trace_fields": list(LEGACY_TRACE_FIELDS),
    }


def upload_dataset(output_dir: Path, repo_id: str, *, create_pr: bool) -> None:
    load_dotenv_if_available()
    operations = [
        CommitOperationAdd(path_in_repo=str(path.relative_to(output_dir)), path_or_fileobj=str(path))
        for path in sorted(output_dir.rglob("*"))
        if path.is_file()
    ]
    HfApi().create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        operations=operations,
        commit_message="Publish curated Impresso media sources NER dataset",
        create_pr=create_pr,
    )


def load_allowed_labels(paths: Iterable[Path]) -> set[str]:
    labels: set[str] = set()
    for path in paths:
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            if row.get("trainable", True) and row.get("label"):
                labels.add(str(row["label"]))
    return labels


def list_files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare and optionally upload the Hugging Face training dataset.")
    parser.add_argument("--input-dir", default="data/curated/legacy-import-curated")
    parser.add_argument("--output-dir", default="/private/tmp/impresso-mediasources-ner-dataset")
    parser.add_argument("--card", default="hf_dataset/README.md")
    parser.add_argument("--repo-id", default="impresso-project/impresso-mediaagencies-ner-dataset")
    parser.add_argument("--newsagencies", default="resources/newsagency_seeds.json")
    parser.add_argument("--radiostations", default="resources/radiostation_seeds.json")
    parser.add_argument("--validate-labels", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-audit", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--create-pr", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "input_dir": str(input_dir),
                    "output_dir": str(output_dir),
                    "repo_id": args.repo_id,
                    "would_copy": [*PRIMARY_FILES, *OPTIONAL_AUDIT_FILES],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    summary = prepare_dataset_repo(
        input_dir=input_dir,
        output_dir=output_dir,
        card_path=Path(args.card),
        repo_id=args.repo_id,
        include_audit=args.include_audit,
        allowed_labels=load_allowed_labels([Path(args.newsagencies), Path(args.radiostations)])
        if args.validate_labels
        else None,
    )
    result = {"output_dir": str(output_dir), "files": list_files(output_dir), "summary": summary}
    if args.upload:
        upload_dataset(output_dir, args.repo_id, create_pr=args.create_pr)
        result["uploaded"] = True
    else:
        result["uploaded"] = False
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
