from lib.validate_curation import main, validate_decisions


def test_validate_decisions_accepts_complete_review() -> None:
    disagreements = [{"review_id": "validation:doc1:abc"}]
    decisions = [
        {
            "_line_number": 1,
            "review_id": "validation:doc1:abc",
            "status": "done",
            "choice": "gold",
            "correct_label": "org.ent.pressagency.havas",
            "reviewer": "tester",
            "reviewed_at": "2026-05-31T12:00:00+02:00",
        }
    ]

    assert validate_decisions(disagreements, decisions, require_complete=True) == []


def test_validate_decisions_rejects_incomplete_and_unknown_ids() -> None:
    disagreements = [{"review_id": "validation:doc1:abc"}]
    decisions = [
        {
            "_line_number": 1,
            "review_id": "validation:doc2:def",
            "status": "done",
            "choice": "prediction",
            "reviewer": "tester",
            "reviewed_at": "2026-05-31T12:00:00+02:00",
        }
    ]

    errors = validate_decisions(disagreements, decisions, require_complete=True)

    assert any("does not exist" in error for error in errors)
    assert any("correct_label is required" in error for error in errors)
    assert any("curation incomplete" in error for error in errors)


def test_validate_curation_allows_missing_decisions_when_incomplete_allowed(tmp_path) -> None:
    disagreements = tmp_path / "all_disagreements.jsonl"
    disagreements.write_text('{"review_id": "validation:doc1:abc"}\n', encoding="utf-8")

    assert (
        main(
            [
                "--disagreements",
                str(disagreements),
                "--decisions",
                str(tmp_path / "missing.jsonl"),
                "--no-require-complete",
            ]
        )
        == 0
    )
