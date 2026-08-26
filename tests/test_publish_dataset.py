import json
from pathlib import Path

from lib.publish_dataset import prepare_dataset_repo
from lib.finalize_dataset_release import finalize_manifest
from lib.promote_dataset_release import copy_projection


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def dataset_row(doc_id: str, split: str) -> dict:
    return {
        "id": doc_id,
        "document_id": doc_id,
        "split": split,
        "language": "fr",
        "source_file": "legacy/source.tsv",
        "source_format": "hipe-tsv",
        "news_agency_as_source": ["Q282656"],
        "segments": [{"iiif_link": "https://example.invalid/iiif"}],
        "sentences": [{"token_start": 0, "token_stop": 2}],
        "tokens": ["Agence", "Havas"],
        "token_start_offsets": [0, 7],
        "token_end_offsets": [6, 12],
        "token_labels": ["B-org.ent.pressagency.havas", "I-org.ent.pressagency.havas"],
        "token_label_ids": [1, 2],
        "audit_marks": [
            {
                "audit_id": "empty-training-docs-v2.0.0",
                "decision": "reject",
                "label": "org.ent.pressagency.tass",
                "start": 21,
                "status": "verified",
                "stop": 28,
            }
        ],
        "token_nel": ["Q282656", "Q282656"],
        "token_ocr": ["", ""],
        "token_render": ["", ""],
        "token_segment_ids": [0, 0],
        "entities": [
            {
                "entity_id": f"{doc_id}#ent-0",
                "label": "org.ent.pressagency.havas",
                "entity_family": "pressagency",
                "label_original": "org.ent.pressagency.havas",
                "status": "accepted",
                "token_start": 0,
                "token_stop": 2,
                "start": 0,
                "stop": 12,
                "surface": "Agence Havas",
                "normalized_surface": "Agence Havvas",
                "nel": "Q282656",
                "wikidata_url": "https://www.wikidata.org/wiki/Q282656",
                "has_ocr_correction": split == "train",
                "max_ocr_levenshtein": 0.25 if split == "train" else 0.0,
            }
        ],
    }


def test_prepare_dataset_repo_writes_hub_layout(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "hub"
    card = tmp_path / "README.md"
    card.write_text("---\npretty_name: Fixture\n---\n\n# Fixture\n", encoding="utf-8")
    for split in ("train", "validation", "test"):
        write_jsonl(input_dir / f"{split}.jsonl", [dataset_row(f"z-doc-{split}", split), dataset_row(f"a-doc-{split}", split)])
    (input_dir / "label_map.json").write_text(
        json.dumps(
            {
                "label2id": {
                    "O": 0,
                    "B-org.ent.pressagency.havas": 1,
                    "I-org.ent.pressagency.havas": 2,
                },
                "id2label": {
                    "0": "O",
                    "1": "B-org.ent.pressagency.havas",
                    "2": "I-org.ent.pressagency.havas",
                },
            }
        ),
        encoding="utf-8",
    )
    (input_dir / "curation_summary.json").write_text('{"applied": 1}\n', encoding="utf-8")
    (input_dir / "manifest.json").write_text('{"status": "ready"}\n', encoding="utf-8")
    (input_dir / "dataset_summary.json").write_text('{"files": []}\n', encoding="utf-8")
    (input_dir / "DATASET_STATISTICS.md").write_text("# Stats\n", encoding="utf-8")
    (input_dir / "DATASET_QUALITY.md").write_text("# Quality\n", encoding="utf-8")

    summary = prepare_dataset_repo(
        input_dir=input_dir,
        output_dir=output_dir,
        card_path=card,
        repo_id="org/dataset",
        allowed_labels={"org.ent.pressagency.havas"},
    )

    assert (output_dir / "README.md").is_file()
    assert (output_dir / "data" / "train.jsonl").is_file()
    assert (output_dir / "label_map.json").is_file()
    assert (output_dir / "DATASET_STATISTICS.md").is_file()
    assert not (output_dir / "dataset_summary.json").exists()
    assert not (output_dir / "audit").exists()
    assert summary["splits"] == {"train": 2, "validation": 2, "test": 2}
    assert summary["entity_labels"] == {"org.ent.pressagency.havas": 6}
    assert summary["legacy_trace_fields"] == ["source_format", "source_file"]
    assert "DATASET_STATISTICS.md" in summary["files"]

    public_train = json.loads((output_dir / "data" / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert public_train["document_id"] == "a-doc-train"
    assert "segments" not in public_train
    assert "sentences" not in public_train
    assert "token_nel" not in public_train
    assert "token_ocr" not in public_train
    assert "token_render" not in public_train
    assert "token_segment_ids" not in public_train
    assert "token_label_ids" not in public_train
    assert public_train["audit_marks"] == [
        {
            "audit_id": "empty-training-docs-v2.0.0",
            "decision": "reject",
            "label": "org.ent.pressagency.tass",
            "start": 21,
            "status": "verified",
            "stop": 28,
        }
    ]
    assert public_train["legacy"] == {
        "source_file": "legacy/source.tsv",
        "source_format": "hipe-tsv",
    }
    assert public_train["entities"] == [
        {
            "entity_family": "pressagency",
            "label": "org.ent.pressagency.havas",
            "ocr_correction": {
                "max_levenshtein": 0.25,
                "surface": "Agence Havvas",
            },
            "start": 0,
            "stop": 12,
            "surface": "Agence Havas",
            "token_start": 0,
            "token_stop": 2,
            "wikidata_url": "https://www.wikidata.org/wiki/Q282656",
        }
    ]


def test_promote_dataset_release_copies_git_projection_without_audit(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    release_dir = tmp_path / "release"
    source_dir.mkdir()
    for name in (
        "train.jsonl",
        "validation.jsonl",
        "test.jsonl",
        "label_map.json",
        "dataset_summary.json",
        "DATASET_STATISTICS.md",
        "DATASET_QUALITY.md",
        "curation_summary.json",
    ):
        (source_dir / name).write_text(f"{name}\n", encoding="utf-8")
    (source_dir / "manifest.json").write_text(
        '{"status": "published", "publication": {"hf_commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}\n',
        encoding="utf-8",
    )

    copied = copy_projection(
        source_dir=source_dir,
        release_dir=release_dir,
        release_files=[
            "train.jsonl",
            "validation.jsonl",
            "test.jsonl",
            "label_map.json",
            "manifest.json",
            "dataset_summary.json",
            "DATASET_STATISTICS.md",
        ],
    )

    assert "curation_summary.json" not in copied
    assert not (release_dir / "curation_summary.json").exists()
    assert (release_dir / "manifest.json").is_file()


def test_promote_dataset_release_requires_published_manifest(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "manifest.json").write_text('{"status": "prerelease"}\n', encoding="utf-8")
    (source_dir / "train.jsonl").write_text("", encoding="utf-8")

    try:
        copy_projection(source_dir=source_dir, release_dir=tmp_path / "release", release_files=["train.jsonl"])
    except ValueError as exc:
        assert "requires manifest status 'published'" in str(exc)
    else:
        raise AssertionError("expected non-ready manifest to fail")


def test_promote_dataset_release_refuses_existing_destination(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    release_dir = tmp_path / "release"
    source_dir.mkdir()
    release_dir.mkdir()
    (source_dir / "manifest.json").write_text(
        '{"status": "published", "publication": {"hf_commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}\n',
        encoding="utf-8",
    )
    (source_dir / "train.jsonl").write_text("", encoding="utf-8")

    try:
        copy_projection(source_dir=source_dir, release_dir=release_dir, release_files=["train.jsonl"])
    except FileExistsError as exc:
        assert "release IDs are immutable" in str(exc)
    else:
        raise AssertionError("expected existing destination to fail")


def test_finalize_dataset_release_records_publication_metadata(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for name in ("train.jsonl", "label_map.json", "dataset_summary.json", "DATASET_STATISTICS.md"):
        (source_dir / name).write_text("", encoding="utf-8")
    (source_dir / "manifest.json").write_text(
        json.dumps({"release_id": "dataset-v2.0.0", "status": "ready", "version": "v2.0.0"}),
        encoding="utf-8",
    )

    manifest = finalize_manifest(
        root=source_dir,
        release_id="dataset-v2.0.0",
        version="v2.0.0",
        repo_id="org/dataset",
        hf_commit_sha="a" * 40,
        hf_revision="v2.0.0",
        hf_release_files=["train.jsonl", "label_map.json"],
        git_release_files=["train.jsonl", "label_map.json", "manifest.json", "dataset_summary.json", "DATASET_STATISTICS.md"],
    )

    assert manifest["status"] == "published"
    assert manifest["publication"] == {
        "dataset_repo": "org/dataset",
        "hf_commit_sha": "a" * 40,
        "hf_revision": "v2.0.0",
    }
    assert manifest["files"]["hf_release"] == ["train.jsonl", "label_map.json"]


def test_finalize_dataset_release_is_idempotent_for_same_publication(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for name in ("train.jsonl", "label_map.json"):
        (source_dir / name).write_text("", encoding="utf-8")
    (source_dir / "manifest.json").write_text(
        json.dumps(
            {
                "release_id": "dataset-v2.0.0",
                "status": "published",
                "version": "v2.0.0",
                "publication": {
                    "dataset_repo": "org/dataset",
                    "hf_commit_sha": "a" * 40,
                    "hf_revision": "v2.0.0",
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = finalize_manifest(
        root=source_dir,
        release_id="dataset-v2.0.0",
        version="v2.0.0",
        repo_id="org/dataset",
        hf_commit_sha="a" * 40,
        hf_revision="v2.0.0",
        hf_release_files=["train.jsonl", "label_map.json"],
        git_release_files=["train.jsonl", "label_map.json"],
    )

    assert manifest["status"] == "published"


def test_finalize_dataset_release_rejects_different_publication_metadata(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "train.jsonl").write_text("", encoding="utf-8")
    (source_dir / "manifest.json").write_text(
        json.dumps(
            {
                "release_id": "dataset-v2.0.0",
                "status": "published",
                "version": "v2.0.0",
                "publication": {
                    "dataset_repo": "org/dataset",
                    "hf_commit_sha": "a" * 40,
                    "hf_revision": "v2.0.0",
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        finalize_manifest(
            root=source_dir,
            release_id="dataset-v2.0.0",
            version="v2.0.0",
            repo_id="org/dataset",
            hf_commit_sha="b" * 40,
            hf_revision="v2.0.0",
            hf_release_files=["train.jsonl"],
            git_release_files=["train.jsonl"],
        )
    except ValueError as exc:
        assert "different publication metadata" in str(exc)
    else:
        raise AssertionError("expected changed publication metadata to fail")
