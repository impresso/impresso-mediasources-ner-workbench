import json
from pathlib import Path

from lib.export_snippet_training_data import export_rows
from lib.recover_cookbook_snippet_decisions import recover_rows
from lib.snippet_data import write_jsonl


def test_recover_rows_rebuilds_missing_decisions_and_preserves_empty_spans(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    current = tmp_path / "reviewed.jsonl"
    label_map = tmp_path / "label_map.json"
    write_jsonl(
        predictions,
        [
            {
                "ci_id": "BBLT-1877-02-23-a-i0106",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ap",
                        "surface": "applause",
                        "lOffset": 5,
                        "rOffset": 13,
                        "confidence_ner": 0.42,
                    }
                ],
            }
        ],
    )
    write_jsonl(
        decisions,
        [
            {
                "review_id": "pressagency-span:cookbook-snippet:BBLT-1877-02-23-a-i0106",
                "candidate_id": "cookbook-snippet:BBLT-1877-02-23-a-i0106",
                "status": "accepted",
                "accepted_spans": [],
                "reviewer": "tester",
                "reviewed_at": "2026-09-04T22:40:10+02:00",
                "notes": "",
            }
        ],
    )
    write_jsonl(current, [])

    rows, rejected, summary = recover_rows(
        predictions_path=predictions,
        decisions_path=decisions,
        current_rows_path=current,
        family="pressagency",
        review_prefix="pressagency-span",
        context_chars=32,
        fetch_content=lambda _ci_id: "Text applause here.",
    )

    assert rejected == []
    assert summary["missing_decisions"] == 1
    assert summary["recovered_candidates"] == 1
    assert len(rows) == 1
    assert rows[0]["accepted_spans"] == []
    assert rows[0]["curation"]["status"] == "accepted"

    reviewed = tmp_path / "reviewed.recovered.jsonl"
    write_jsonl(reviewed, rows)
    label_map.write_text(
        json.dumps({"label2id": {"O": 0, "B-org.ent.pressagency.ap": 1}, "id2label": {"0": "O", "1": "B-org.ent.pressagency.ap"}}),
        encoding="utf-8",
    )

    exported = export_rows(reviewed, label_map)

    assert len(exported) == 1
    assert exported[0]["entities"] == []
    assert exported[0]["quality_flags"] == ["reviewed_negative_snippet"]
