from pathlib import Path

from lib.review_curation import latest_decisions, pending_items, suggested_label


def test_pending_items_skips_done_decisions() -> None:
    disagreements = [{"review_id": "a"}, {"review_id": "b"}]
    decisions = {"a": {"review_id": "a", "status": "done"}}

    assert pending_items(disagreements, decisions) == [{"review_id": "b"}]


def test_latest_decisions_uses_last_decision(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        '{"review_id": "a", "status": "done", "choice": "gold"}\n'
        '{"review_id": "a", "status": "done", "choice": "prediction"}\n',
        encoding="utf-8",
    )

    assert latest_decisions(path)["a"]["choice"] == "prediction"


def test_suggested_label_returns_selected_entity_label() -> None:
    item = {
        "gold": {"label": "org.ent.pressagency.havas"},
        "prediction": {"label": "org.ent.pressagency.afp"},
    }

    assert suggested_label(item, "gold") == "org.ent.pressagency.havas"
    assert suggested_label(item, "prediction") == "org.ent.pressagency.afp"
