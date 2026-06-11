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


def test_validate_decisions_ignores_stale_ids_and_rejects_current_errors() -> None:
    disagreements = [
        {"review_id": "validation:doc1:abc"},
        {"review_id": "validation:doc2:def", "prediction": {"label": "org.ent.pressagency.havas"}},
    ]
    decisions = [
        {
            "_line_number": 1,
            "review_id": "validation:doc2:def",
            "status": "done",
            "choice": "prediction",
            "reviewer": "tester",
            "reviewed_at": "2026-05-31T12:00:00+02:00",
        },
        {
            "_line_number": 2,
            "review_id": "validation:doc3:ghi",
            "status": "done",
            "choice": "gold",
            "reviewer": "tester",
            "reviewed_at": "2026-05-31T12:00:00+02:00",
        },
    ]

    errors = validate_decisions(disagreements, decisions, require_complete=True)

    assert not any("does not exist" in error for error in errors)
    assert any("correct_label is required" in error for error in errors)
    assert any("curation incomplete" in error for error in errors)


def test_validate_decisions_allows_selected_none_side_without_correct_label() -> None:
    disagreements = [
        {
            "review_id": "validation:doc1:abc",
            "gold": None,
            "prediction": {"label": "org.ent.pressagency.havas"},
        },
        {
            "review_id": "validation:doc2:def",
            "gold": {"label": "org.ent.pressagency.havas"},
            "prediction": None,
        },
    ]
    decisions = [
        {
            "_line_number": 1,
            "review_id": "validation:doc1:abc",
            "status": "done",
            "choice": "gold",
            "correct_label": "",
            "reviewer": "tester",
            "reviewed_at": "2026-05-31T12:00:00+02:00",
        },
        {
            "_line_number": 2,
            "review_id": "validation:doc2:def",
            "status": "done",
            "choice": "prediction",
            "correct_label": "",
            "reviewer": "tester",
            "reviewed_at": "2026-05-31T12:00:00+02:00",
        },
    ]

    assert validate_decisions(disagreements, decisions, require_complete=True) == []


def test_validate_decisions_uses_latest_status_and_allows_todo() -> None:
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
        },
        {
            "_line_number": 2,
            "review_id": "validation:doc1:abc",
            "status": "todo",
        },
    ]

    complete_errors = validate_decisions(disagreements, decisions, require_complete=True)
    snapshot_errors = validate_decisions(disagreements, decisions, require_complete=False)

    assert any("curation incomplete" in error for error in complete_errors)
    assert snapshot_errors == []


def test_validate_decisions_accepts_ignored_skip_as_complete() -> None:
    disagreements = [{"review_id": "validation:doc1:abc"}]
    decisions = [
        {
            "_line_number": 1,
            "review_id": "validation:doc1:abc",
            "status": "ignored",
            "choice": "skip",
            "reviewer": "tester",
            "reviewed_at": "2026-05-31T12:00:00+02:00",
        }
    ]

    assert validate_decisions(disagreements, decisions, require_complete=True) == []


def test_validate_decisions_rejects_done_skip() -> None:
    disagreements = [{"review_id": "validation:doc1:abc"}]
    decisions = [
        {
            "_line_number": 1,
            "review_id": "validation:doc1:abc",
            "status": "done",
            "choice": "skip",
            "reviewer": "tester",
            "reviewed_at": "2026-05-31T12:00:00+02:00",
        }
    ]

    errors = validate_decisions(disagreements, decisions, require_complete=True)

    assert any("skip decisions must use status=ignored" in error for error in errors)


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
