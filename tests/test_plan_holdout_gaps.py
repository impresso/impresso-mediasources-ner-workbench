import json

from lib.plan_holdout_gaps import build_plan


def test_holdout_plan_oversamples_without_changing_exact_deficit(tmp_path) -> None:
    seeds = tmp_path / "seeds.json"
    validation = tmp_path / "validation.jsonl"
    test = tmp_path / "test.jsonl"
    seeds.write_text(json.dumps([{"label": "org.ent.pressagency.example", "aliases": ["Example"]}]), encoding="utf-8")
    validation.write_text("", encoding="utf-8")
    test.write_text("", encoding="utf-8")

    plan = build_plan(seeds, validation, test, "pressagency", 5, ["en"], 1, 1.5)

    assert plan["gaps"][0]["needed"] == 10
    assert plan["gaps"][0]["planned_candidates"] == 15
    assert plan["rows"][0]["planned_new"] == 15
