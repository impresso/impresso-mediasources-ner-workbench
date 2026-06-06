import json
from pathlib import Path

import pytest

from lib.promote_snippet_splits import main


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
