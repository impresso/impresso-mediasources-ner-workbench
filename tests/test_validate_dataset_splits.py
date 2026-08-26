import json
from pathlib import Path

from lib.validate_dataset_splits import load_current_targets, main, validate_splits


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_validate_splits_reports_cross_split_duplicates(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    test = tmp_path / "test.jsonl"
    write_jsonl(train, [{"document_id": "doc-a", "split": "train"}])
    write_jsonl(validation, [{"document_id": "doc-b"}])
    write_jsonl(test, [{"document_id": "doc-a", "split": "test"}])

    summary = validate_splits({"train": train, "validation": validation, "test": test})

    assert summary["rows"] == {"train": 1, "validation": 1, "test": 1}
    assert summary["duplicate_document_ids_across_splits"] == {"doc-a": ["train", "test"]}
    assert summary["duplicate_locations"]["doc-a"] == [
        {"line": 1, "path": str(train), "row_split": "train", "source_component": "", "split": "train"},
        {"line": 1, "path": str(test), "row_split": "test", "source_component": "", "split": "test"},
    ]
    assert summary["removal_hints"][0]["keep"]["path"] == str(train)
    assert summary["removal_hints"][0]["remove"][0]["path"] == str(test)


def test_validate_dataset_splits_returns_nonzero_for_duplicates(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    test = tmp_path / "test.jsonl"
    write_jsonl(train, [{"document_id": "doc-a"}])
    write_jsonl(validation, [])
    write_jsonl(test, [{"document_id": "doc-a"}])

    assert main(["--train", str(train), "--validation", str(validation), "--test", str(test)]) == 1


def test_validate_splits_uses_current_snippet_target_for_removal_hint(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    test = tmp_path / "test.jsonl"
    snippet_test = tmp_path / "snippet_test.jsonl"
    write_jsonl(train, [{"document_id": "doc-a", "split": "train"}])
    write_jsonl(validation, [])
    write_jsonl(test, [{"document_id": "doc-a", "split": "test"}])
    write_jsonl(snippet_test, [{"document_id": "doc-a"}])

    summary = validate_splits(
        {"train": train, "validation": validation, "test": test},
        current_targets=load_current_targets([("test", snippet_test)]),
    )

    assert summary["removal_hints"][0]["keep"]["path"] == str(test)
    assert summary["removal_hints"][0]["remove"][0]["path"] == str(train)
