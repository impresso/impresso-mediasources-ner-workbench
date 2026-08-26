import json
from pathlib import Path

from lib.curation_state import build_state, parse_args
from lib.snippet_data import write_jsonl


def test_curation_state_counts_snippet_pipeline(tmp_path: Path) -> None:
    news_candidates = tmp_path / "news_candidates.jsonl"
    news_scored = tmp_path / "news_scored.jsonl"
    news_reviewed = tmp_path / "news_reviewed.jsonl"
    news_decisions = tmp_path / "news_decisions.jsonl"
    news_train = tmp_path / "news_train.jsonl"
    news_validation = tmp_path / "news_validation.jsonl"
    news_test = tmp_path / "news_test.jsonl"
    radio_candidates = tmp_path / "radio_candidates.jsonl"
    radio_scored = tmp_path / "radio_scored.jsonl"
    radio_reviewed = tmp_path / "radio_reviewed.jsonl"
    radio_decisions = tmp_path / "radio_decisions.jsonl"
    radio_train = tmp_path / "radio_train.jsonl"
    radio_validation = tmp_path / "radio_validation.jsonl"
    radio_test = tmp_path / "radio_test.jsonl"

    write_jsonl(news_candidates, [{"id": "n1"}, {"id": "n2"}])
    write_jsonl(
        news_scored,
        [
            {
                "id": "n1",
                "curation": {"status": "auto_accepted"},
                "model": {"predicted_spans": [{"label": "org.ent.pressagency.havas"}]},
                "accepted_spans": [{"label": "org.ent.pressagency.havas"}],
            },
            {"id": "n2", "curation": {"status": "needs_review"}, "model": {"predicted_spans": []}},
        ],
    )
    write_jsonl(
        news_reviewed,
        [
            {
                "id": "n1",
                "curation": {"status": "accepted"},
                "model": {"predicted_spans": [{"label": "org.ent.pressagency.havas"}]},
                "accepted_spans": [{"label": "org.ent.pressagency.havas"}],
            }
        ],
    )
    write_jsonl(news_decisions, [{"review_id": "newsagency-snippet:n1", "status": "accepted"}])
    write_jsonl(
        news_train,
        [
            {
                "id": "n1",
                "tokens": ["Havas"],
                "entities": [{"label": "org.ent.pressagency.havas"}],
            }
        ],
    )
    write_jsonl(
        news_validation,
        [
            {
                "id": "n3",
                "tokens": ["Reuters"],
                "entities": [{"label": "org.ent.pressagency.reuters"}],
            }
        ],
    )
    write_jsonl(news_test, [])
    write_jsonl(radio_candidates, [{"id": "r1"}])
    write_jsonl(radio_scored, [{"id": "r1", "curation": {"status": "needs_review"}, "model": {"predicted_spans": []}}])
    write_jsonl(radio_reviewed, [])
    write_jsonl(radio_decisions, [])
    write_jsonl(radio_train, [])
    write_jsonl(radio_validation, [])
    write_jsonl(radio_test, [])

    args = parse_args(
        [
            "--newsagency-snippets",
            str(news_candidates),
            "--newsagency-scored-snippets",
            str(news_scored),
            "--newsagency-reviewed-snippets",
            str(news_reviewed),
            "--newsagency-snippet-decisions",
            str(news_decisions),
            "--newsagency-snippet-train-jsonl",
            str(news_train),
            "--newsagency-snippet-validation-jsonl",
            str(news_validation),
            "--newsagency-snippet-test-jsonl",
            str(news_test),
            "--radiostation-snippets",
            str(radio_candidates),
            "--radiostation-scored-snippets",
            str(radio_scored),
            "--radiostation-reviewed-snippets",
            str(radio_reviewed),
            "--radiostation-snippet-decisions",
            str(radio_decisions),
            "--radiostation-snippet-train-jsonl",
            str(radio_train),
            "--radiostation-snippet-validation-jsonl",
            str(radio_validation),
            "--radiostation-snippet-test-jsonl",
            str(radio_test),
            "--dataset-output-dir",
            str(tmp_path / "staging"),
            "--curation-output-dir",
            str(tmp_path / "legacy-curation"),
            "--curation-input-dir",
            str(tmp_path / "legacy-import"),
            "--curation-applied-dir",
            str(tmp_path / "legacy-applied"),
        ]
    )

    state = build_state(args)

    news = state["snippets"]["newsagencies"]
    radio = state["snippets"]["radiostations"]
    assert news["candidates"]["rows"] == 2
    assert news["scored"]["statuses"] == {"auto_accepted": 1, "needs_review": 1}
    assert news["reviewed"]["statuses"] == {"accepted": 1}
    assert news["decisions"]["rows"] == 1
    assert news["split"]["total_rows"] == 2
    assert news["split"]["total_entities"] == 2
    assert news["exported"]["total_rows"] == 2
    assert news["exported"]["total_entities"] == 2
    assert news["workflow"]["pending_review"] == 1
    assert news["workflow"]["curated"] == 1
    assert news["workflow"]["accepted_for_dataset"] == 1
    assert news["workflow"]["trainable_for_dataset"] == 1
    assert news["workflow"]["split_rows"] == 2
    assert news["workflow"]["next_action"] == "review snippets"
    assert radio["candidates"]["rows"] == 1
    assert radio["scored"]["statuses"] == {"needs_review": 1}
    assert radio["workflow"]["pending_review"] == 1
    assert radio["workflow"]["next_action"] == "review snippets"


def test_curation_state_reads_staging_dataset_summary(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "dataset_summary.json").write_text(
        json.dumps({"splits": {"train": 2}, "entities_by_split": {"train": 3}, "label_count": 4}),
        encoding="utf-8",
    )

    args = parse_args(["--dataset-output-dir", str(staging), "--dataset", "org/dataset", "--dataset-revision", "abc123"])

    state = build_state(args)

    assert state["dataset"]["staging_summary"]["splits"] == {"train": 2}
    assert state["dataset"]["published"]["repo_id"] == "org/dataset"
    assert state["dataset"]["published"]["configured_revision"] == "abc123"
    assert state["dataset"]["published"]["remote_checked"] is False
