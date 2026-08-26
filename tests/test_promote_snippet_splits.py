import json
from pathlib import Path

import pytest

from lib.promote_snippet_splits import duplicate_ids_across_splits, main


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_promote_snippets_appends_replaces_and_sorts(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    snippets = tmp_path / "snippet_train.jsonl"
    summary = tmp_path / "summary.json"
    write_jsonl(
        train,
        [
            {"document_id": "b-doc", "text": "base b"},
            {"document_id": "c-doc", "text": "base c"},
        ],
    )
    write_jsonl(
        snippets,
        [
            {"document_id": "a-doc", "text": "snippet a", "source_component": "newsagency_snippet_manual"},
            {"document_id": "c-doc", "text": "snippet c", "source_component": "radiostation_snippet_manual"},
        ],
    )

    main(["--base", f"train={train}", "--snippet", f"train={snippets}", "--summary-json", str(summary)])

    rows = read_jsonl(train)
    assert [row["document_id"] for row in rows] == ["a-doc", "b-doc", "c-doc"]
    assert rows[2]["text"] == "snippet c"

    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["splits"]["train"]["added"] == 1
    assert data["splits"]["train"]["replaced"] == 1
    assert data["splits"]["train"]["output_rows"] == 3


def test_promote_snippets_compacts_dataset_rows(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    snippets = tmp_path / "snippet_train.jsonl"
    write_jsonl(
        train,
        [
            {
                "document_id": "old-doc",
                "text": "base",
                "tokens": ["base"],
                "token_label_ids": [0],
                "source_component": "newsagency_snippet_auto",
                "entities": [
                    {
                        "entity_id": "old-doc#ent-0",
                        "label": "org.ent.pressagency.havas",
                        "entity_family": "pressagency",
                        "token_start": 0,
                        "token_stop": 1,
                        "start": 0,
                        "stop": 4,
                        "surface": "base",
                        "normalized_surface": "base",
                        "has_ocr_correction": False,
                        "max_ocr_levenshtein": 0.0,
                    }
                ],
            }
        ],
    )
    write_jsonl(
        snippets,
        [
            {
                "document_id": "new-doc",
                "text": "snippet",
                "source_component": "newsagency_snippet_manual",
                "token_label_ids": [0],
                "entities": [{"entity_id": "new-doc#ent-0", "label": "org.ent.pressagency.havas"}],
            }
        ],
    )

    main(["--base", f"train={train}", "--snippet", f"train={snippets}"])

    rows = read_jsonl(train)
    assert "token_label_ids" not in rows[0]
    assert "source_component" not in rows[0]
    assert "entity_id" not in rows[0]["entities"][0]
    assert "normalized_surface" not in rows[0]["entities"][0]
    assert "token_label_ids" not in rows[1]
    assert "source_component" not in rows[1]
    assert "entity_id" not in rows[1]["entities"][0]


def test_promote_snippets_dry_run_does_not_write(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    snippets = tmp_path / "snippet_train.jsonl"
    write_jsonl(train, [{"document_id": "b-doc", "text": "base b"}])
    write_jsonl(snippets, [{"document_id": "a-doc", "text": "snippet a"}])

    main(["--dry-run", "--base", f"train={train}", "--snippet", f"train={snippets}"])

    assert read_jsonl(train) == [{"document_id": "b-doc", "text": "base b"}]


def test_promote_snippets_rejects_duplicate_snippet_ids(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    snippets = tmp_path / "snippet_train.jsonl"
    write_jsonl(train, [{"document_id": "b-doc", "text": "base b"}])
    write_jsonl(
        snippets,
        [
            {"document_id": "a-doc", "text": "snippet a"},
            {"document_id": "a-doc", "text": "snippet a again"},
        ],
    )

    with pytest.raises(ValueError, match="duplicate snippet document_id"):
        main(["--base", f"train={train}", "--snippet", f"train={snippets}"])


def test_duplicate_ids_across_train_validation_test_are_reported() -> None:
    duplicates = duplicate_ids_across_splits(
        {
            "train": [{"document_id": "doc-a"}, {"document_id": "doc-b"}],
            "validation": [{"document_id": "doc-b"}],
            "test": [{"document_id": "doc-c"}, {"document_id": "doc-a"}],
        }
    )

    assert duplicates == {"doc-a": ["test", "train"], "doc-b": ["train", "validation"]}


def test_promote_snippets_rejects_duplicate_ids_across_splits_before_writing(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    test = tmp_path / "test.jsonl"
    write_jsonl(train, [{"document_id": "doc-a", "text": "train"}])
    write_jsonl(validation, [{"document_id": "doc-a", "text": "validation"}])
    write_jsonl(test, [{"document_id": "doc-c", "text": "test"}])

    with pytest.raises(ValueError, match="duplicate document_id values across train/validation/test splits"):
        main(["--base", f"train={train}", "--base", f"validation={validation}", "--base", f"test={test}"])

    assert read_jsonl(train) == [{"document_id": "doc-a", "text": "train"}]
    assert read_jsonl(validation) == [{"document_id": "doc-a", "text": "validation"}]
    assert read_jsonl(test) == [{"document_id": "doc-c", "text": "test"}]


def test_promote_snippets_moves_refreshed_snippet_to_current_split(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    test = tmp_path / "test.jsonl"
    snippet_validation = tmp_path / "snippet_validation.jsonl"
    summary = tmp_path / "summary.json"
    write_jsonl(train, [{"document_id": "doc-a", "text": "old train copy"}])
    write_jsonl(validation, [])
    write_jsonl(test, [{"document_id": "doc-c", "text": "test"}])
    write_jsonl(snippet_validation, [{"document_id": "doc-a", "text": "new validation copy"}])

    main(
        [
            "--base",
            f"train={train}",
            "--base",
            f"validation={validation}",
            "--base",
            f"test={test}",
            "--snippet",
            f"validation={snippet_validation}",
            "--summary-json",
            str(summary),
        ]
    )

    assert read_jsonl(train) == []
    assert read_jsonl(validation) == [{"document_id": "doc-a", "entities": [], "text": "new validation copy"}]
    assert read_jsonl(test) == [{"document_id": "doc-c", "entities": [], "text": "test"}]
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["splits"]["train"]["removed_refreshed_from_old_split"] == 1
    assert data["duplicate_document_ids_across_splits"] == {}


def test_promote_snippets_rejects_duplicate_snippet_ids_across_exported_splits(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    snippet_train = tmp_path / "snippet_train.jsonl"
    snippet_validation = tmp_path / "snippet_validation.jsonl"
    write_jsonl(train, [])
    write_jsonl(validation, [])
    write_jsonl(snippet_train, [{"document_id": "doc-a", "text": "train snippet"}])
    write_jsonl(snippet_validation, [{"document_id": "doc-a", "text": "validation snippet"}])

    with pytest.raises(ValueError, match="duplicate snippet document_id values across exported snippet splits"):
        main(
            [
                "--base",
                f"train={train}",
                "--base",
                f"validation={validation}",
                "--snippet",
                f"train={snippet_train}",
                "--snippet",
                f"validation={snippet_validation}",
            ]
        )
