from __future__ import annotations

import pytest

from lib.clean_workbench import clean, collect_clean_items, ensure_inside_repo


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")


def test_clean_removes_generated_roots_and_local_data(tmp_path):
    touch(tmp_path / "staging.d" / "reports" / "state.json")
    touch(tmp_path / "models.d" / "checkpoint" / "config.json")
    touch(tmp_path / ".hf" / "cache.json")
    touch(tmp_path / "data" / "mlm" / "source" / "de.jsonl")
    touch(tmp_path / "data" / "candidates" / ".gitkeep")
    touch(tmp_path / "data" / "candidates" / "sample.jsonl")
    touch(tmp_path / "data" / "curated" / "snippets" / "decisions.jsonl")
    touch(tmp_path / "data" / "testset" / "local.jsonl")
    touch(tmp_path / "data" / "releases" / "dataset-v2.0.0" / "train.jsonl")

    result = clean(tmp_path, dry_run=False)

    removed = {item["path"] for item in result["items"]}
    assert "staging.d" in removed
    assert "models.d" in removed
    assert ".hf" in removed
    assert "data/mlm" in removed
    assert "data/candidates/sample.jsonl" in removed
    assert "data/curated/snippets" in removed
    assert "data/testset/local.jsonl" in removed
    assert not (tmp_path / "staging.d").exists()
    assert not (tmp_path / "data" / "curated" / "snippets").exists()
    assert (tmp_path / "data" / "candidates" / ".gitkeep").is_file()
    assert (tmp_path / "data" / "releases" / "dataset-v2.0.0" / "train.jsonl").is_file()


def test_clean_dry_run_reports_without_removing(tmp_path):
    touch(tmp_path / "cache.d" / "runtime.json")
    touch(tmp_path / "data" / "curated" / "annotation_coverage.json")

    result = clean(tmp_path, dry_run=True)

    assert result["count"] == 2
    assert (tmp_path / "cache.d" / "runtime.json").is_file()
    assert (tmp_path / "data" / "curated" / "annotation_coverage.json").is_file()


def test_collect_preserves_gitkeep(tmp_path):
    touch(tmp_path / "data" / "candidates" / ".gitkeep")

    assert collect_clean_items(tmp_path) == []


def test_ensure_inside_repo_rejects_outside_path(tmp_path):
    outside = tmp_path.parent / "outside-clean-target"

    with pytest.raises(ValueError, match="outside repository"):
        ensure_inside_repo(tmp_path, outside)
