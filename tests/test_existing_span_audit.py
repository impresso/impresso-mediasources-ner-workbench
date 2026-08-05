import json
from pathlib import Path

from lib.apply_span_patch_decisions import apply_span_patches
from lib.audit_existing_spans import build_candidates, write_jsonl
from lib.span_patch_review import decision_record, load_span_patches, write_jsonl as write_review_jsonl


LABEL = "org.ent.pressagency.havas"


def source_row() -> dict:
    text = "Agence Havas annonce."
    return {
        "date": "1938-01-01",
        "document_id": "doc-1",
        "entities": [
            {
                "entity_family": "pressagency",
                "label": LABEL,
                "start": 7,
                "stop": 12,
                "surface": "Havas",
                "token_start": 1,
                "token_stop": 2,
            }
        ],
        "language": "fr",
        "newspaper": "EXP",
        "text": text,
        "token_end_offsets": [6, 12, 21],
        "token_labels": ["O", f"B-{LABEL}", "O"],
        "token_start_offsets": [0, 7, 13],
        "tokens": ["Agence", "Havas", "annonce."],
    }


def write_source(path: Path) -> None:
    write_jsonl(path, [source_row()])


def test_existing_span_audit_builds_candidates_for_target_label(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    write_source(source)

    candidates, tsv_rows, summary = build_candidates(source, target_label=LABEL, audit_id="existing-havas")

    assert summary["candidate_spans"] == 1
    assert summary["candidate_documents"] == 1
    assert tsv_rows[0]["surface"] == "Havas"
    assert candidates[0]["audit_mode"] == "existing-span-boundary"
    assert candidates[0]["candidate_spans"][0]["token_start"] == 1


def test_existing_span_audit_limit_reports_non_exhaustive_queue(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    rows = []
    for index in range(3):
        row = source_row()
        row["document_id"] = f"doc-{index}"
        rows.append(row)
    write_jsonl(source, rows)

    candidates, tsv_rows, summary = build_candidates(source, target_label=LABEL, audit_id="existing-havas", limit=2)

    assert len(candidates) == 2
    assert len(tsv_rows) == 2
    assert summary["candidate_spans"] == 2
    assert summary["total_candidate_spans"] == 3
    assert summary["omitted_candidate_spans"] == 1
    assert summary["exhaustive"] is False
    assert summary["candidate_spans_by_language"] == {"fr": 2}
    assert summary["total_candidate_spans_by_language"] == {"fr": 3}


def test_existing_span_accept_only_adds_audit_mark(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    candidates_path = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    write_source(source)
    candidates, _tsv_rows, _summary = build_candidates(source, target_label=LABEL, audit_id="existing-havas")
    write_review_jsonl(candidates_path, candidates)
    patch = load_span_patches(candidates_path, audit_id="existing-havas", target_label=LABEL)[0]
    write_review_jsonl(decisions_path, [decision_record(patch, choice="accept", reviewer="tester")])

    result = apply_span_patches(
        input_jsonl=source,
        output_jsonl=tmp_path / "patched.jsonl",
        candidates_path=candidates_path,
        decisions_path=decisions_path,
        audit_id="existing-havas",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
        target_label=LABEL,
        replace_overlaps=True,
    )

    rows = [json.loads(line) for line in (tmp_path / "patched.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["entities"] == source_row()["entities"]
    assert rows[0]["audit_marks"][0]["decision"] == "accept"
    assert result["audit_marks_written"] == 1
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["applied"] == 0


def test_existing_span_modify_replaces_boundary(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    candidates_path = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    write_source(source)
    candidates, _tsv_rows, _summary = build_candidates(source, target_label=LABEL, audit_id="existing-havas")
    write_review_jsonl(candidates_path, candidates)
    patch = load_span_patches(candidates_path, audit_id="existing-havas", target_label=LABEL)[0]
    write_review_jsonl(
        decisions_path,
        [
            decision_record(
                patch,
                choice="modify",
                reviewer="tester",
                correct_label=LABEL,
                start=0,
                stop=12,
                token_start=0,
                token_stop=2,
            )
        ],
    )

    apply_span_patches(
        input_jsonl=source,
        output_jsonl=tmp_path / "patched.jsonl",
        candidates_path=candidates_path,
        decisions_path=decisions_path,
        audit_id="existing-havas",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
        target_label=LABEL,
        replace_overlaps=True,
    )

    rows = [json.loads(line) for line in (tmp_path / "patched.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["entities"][0]["start"] == 0
    assert rows[0]["entities"][0]["surface"] == "Agence Havas"
    assert rows[0]["token_labels"] == [f"B-{LABEL}", f"I-{LABEL}", "O"]


def test_existing_span_reject_removes_annotation(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    candidates_path = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    write_source(source)
    candidates, _tsv_rows, _summary = build_candidates(source, target_label=LABEL, audit_id="existing-havas")
    write_review_jsonl(candidates_path, candidates)
    patch = load_span_patches(candidates_path, audit_id="existing-havas", target_label=LABEL)[0]
    write_review_jsonl(decisions_path, [decision_record(patch, choice="reject", reviewer="tester")])

    apply_span_patches(
        input_jsonl=source,
        output_jsonl=tmp_path / "patched.jsonl",
        candidates_path=candidates_path,
        decisions_path=decisions_path,
        audit_id="existing-havas",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
        target_label=LABEL,
        replace_overlaps=True,
    )

    rows = [json.loads(line) for line in (tmp_path / "patched.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["entities"] == []
    assert rows[0]["token_labels"] == ["O", "O", "O"]
