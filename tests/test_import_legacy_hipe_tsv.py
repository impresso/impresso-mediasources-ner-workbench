from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.import_legacy_hipe_tsv import run_conversion

FIXTURE = ROOT / "tests" / "fixtures" / "legacy_hipe_sample.tsv"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run_fixture_conversion(output: Path) -> dict:
    args = argparse.Namespace(
        input=[str(FIXTURE)],
        output=str(output),
        source_root=str(ROOT),
        split="validation",
        newsagency_seeds=str(ROOT / "resources" / "newsagency_seeds.json"),
        forbidden_label_policy="exclude",
        unknown_label_policy="error",
        malformed_bio_policy="error",
        duplicate_policy="error",
        allow_missing_metadata=False,
    )
    return run_conversion(args)


def test_import_removes_forbidden_legacy_labels() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir)
        report = run_fixture_conversion(output)
        rows = load_jsonl(output / "validation.jsonl")
        excluded = load_jsonl(output / "audit" / "excluded_entities.jsonl")
        label_map = json.loads((output / "label_map.json").read_text(encoding="utf-8"))

    labels = {label for row in rows for label in row["token_labels"]}
    entity_labels = {entity["label"] for row in rows for entity in row["entities"]}
    forbidden_fragments = ["pressagency.unk", "pressagency.ag", "pers.ind.articleauthor"]
    assert all(not any(fragment in label for fragment in forbidden_fragments) for label in labels)
    assert all(not any(fragment in label for fragment in forbidden_fragments) for label in entity_labels)
    assert all(not any(fragment in label for fragment in forbidden_fragments) for label in label_map["label2id"])
    assert label_map["label2id"]["O"] == 0
    assert report["excluded_entity_counts_by_reason"] == {
        "article_author": 1,
        "generic_agency_marker": 1,
        "unknown_agency": 1,
    }
    assert {row["reason"] for row in excluded} == {
        "article_author",
        "generic_agency_marker",
        "unknown_agency",
    }


def test_import_preserves_offsets_entities_and_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir)
        run_fixture_conversion(output)
        rows = load_jsonl(output / "validation.jsonl")

    first = rows[0]
    assert first["language"] == "de"
    assert first["newspaper"] == "DTT"
    assert first["news_agency_as_source"] == ["Q493845"]
    assert first["entities"][0]["surface"] == "United Preß"
    assert first["entities"][0]["label"] == "org.ent.pressagency.up-upi"
    assert first["entities"][0]["nel"] == "Q493845"
    assert first["text"][first["entities"][0]["start"] : first["entities"][0]["stop"]] == "United Preß"
    assert len(first["token_label_ids"]) == len(first["tokens"])

    reuters = rows[1]
    assert reuters["entities"][0]["surface"] == "Reutei"
    assert reuters["entities"][0]["normalized_surface"] == "Reuter"
    assert reuters["entities"][0]["has_ocr_correction"] is True
    assert reuters["quality_flags"] == ["has_forbidden_legacy_labels", "has_ocr_corrections"]

    dnb = rows[2]
    assert dnb["text"].startswith("D.N.B. Ende")
    assert dnb["entities"][0]["surface"] == "D.N.B."
    assert dnb["entities"][0]["label"] == "org.ent.pressagency.dnb"
    for token, start, stop in zip(dnb["tokens"], dnb["token_start_offsets"], dnb["token_end_offsets"], strict=True):
        assert dnb["text"][start:stop] == token


if __name__ == "__main__":
    test_import_removes_forbidden_legacy_labels()
    test_import_preserves_offsets_entities_and_metadata()
