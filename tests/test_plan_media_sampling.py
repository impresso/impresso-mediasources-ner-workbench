import json
from pathlib import Path

from lib.plan_media_sampling import planned_rows
from lib.sample_newsagencies import load_sampling_plan_queries


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_planner_subtracts_pending_work_and_prefers_underrepresented_surface(tmp_path: Path) -> None:
    seeds = tmp_path / "seeds.json"
    coverage = tmp_path / "coverage.json"
    profiles = tmp_path / "profiles.json"
    pending = tmp_path / "pending.jsonl"

    write_json(
        seeds,
        [
            {
                "canonical_id": "havas",
                "label": "org.ent.pressagency.havas",
                "display_name": "Havas",
                "trainable": True,
                "aliases": ["Havas", "Agence Havas"],
                "aliases_by_language": {"fr": ["Agence Havas"]},
            }
        ],
    )
    write_json(
        coverage,
        {
            "rows": [
                {
                    "family": "pressagency",
                    "label": "org.ent.pressagency.havas",
                    "languages": {"fr": {"missing_to_target": 4, "target": 20, "total": 16, "dataset": 16}},
                }
            ]
        },
    )
    write_json(
        profiles,
        {
            "profiles": [
                {
                    "label": "org.ent.pressagency.havas",
                    "top_surfaces": [
                        {"normalized_surface": "havas", "languages": {"fr": 12}},
                        {"normalized_surface": "agence havas", "languages": {"fr": 0}},
                    ],
                }
            ]
        },
    )
    write_jsonl(
        pending,
        [
            {"id": "sample-1", "candidate_label": "org.ent.pressagency.havas", "search_language": "fr"},
        ],
    )

    rows, skipped = planned_rows(
        seeds_path=seeds,
        coverage_path=coverage,
        profiles_path=profiles,
        pending_paths=[pending],
        family="pressagency",
        languages=["fr"],
        labels=None,
        max_queries_per_bucket=1,
        target_per_bucket=2,
        max_per_label=5,
        min_missing=1,
        surface_saturation=5,
    )

    assert skipped == []
    assert len(rows) == 1
    assert rows[0]["query"] == "Agence Havas"
    assert rows[0]["missing"] == 4
    assert rows[0]["pending"] == 1
    assert rows[0]["planned_new"] == 2
    assert rows[0]["reason"] == "underrepresented_surface"


def test_planner_skips_bucket_when_pending_work_fills_gap(tmp_path: Path) -> None:
    seeds = tmp_path / "seeds.json"
    coverage = tmp_path / "coverage.json"
    profiles = tmp_path / "profiles.json"
    pending = tmp_path / "pending.jsonl"
    label = "org.ent.pressagency.havas"

    write_json(seeds, [{"canonical_id": "havas", "label": label, "display_name": "Havas", "trainable": True, "aliases": ["Havas"]}])
    write_json(
        coverage,
        {"rows": [{"family": "pressagency", "label": label, "languages": {"fr": {"missing_to_target": 1, "target": 20, "total": 19}}}]},
    )
    write_json(profiles, {"profiles": []})
    write_jsonl(
        pending,
        [
            {"id": "sample-1", "candidate_label": label, "search_language": "fr"},
        ],
    )

    rows, skipped = planned_rows(
        seeds_path=seeds,
        coverage_path=coverage,
        profiles_path=profiles,
        pending_paths=[pending],
        family="pressagency",
        languages=["fr"],
        labels=None,
        max_queries_per_bucket=1,
        target_per_bucket=2,
        max_per_label=5,
        min_missing=1,
        surface_saturation=5,
    )

    assert rows == []
    assert skipped[0]["reason"] == "pending_work_fills_gap"


def test_load_sampling_plan_queries_groups_languages(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    write_json(
        plan,
        {
            "rows": [
                {
                    "family": "pressagency",
                    "label": "org.ent.pressagency.havas",
                    "canonical_id": "havas",
                    "display_name": "Havas",
                    "query": "Agence Havas",
                    "language": "fr",
                    "planned_new": 2,
                },
                {
                    "family": "pressagency",
                    "label": "org.ent.pressagency.havas",
                    "canonical_id": "havas",
                    "display_name": "Havas",
                    "query": "Agence Havas",
                    "language": "de",
                    "planned_new": 1,
                },
            ]
        },
    )

    queries, targets = load_sampling_plan_queries(plan)

    assert queries == [
        {
            "canonical_id": "havas",
            "display_name": "Havas",
            "label": "org.ent.pressagency.havas",
            "planned_languages": {"de": 1, "fr": 2},
            "query": "Agence Havas",
        }
    ]
    assert targets[("org.ent.pressagency.havas", "Agence Havas", "fr")] == 2
    assert targets[("org.ent.pressagency.havas", "Agence Havas", "de")] == 1
