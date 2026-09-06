from __future__ import annotations

import bz2
import json
from collections import Counter
from pathlib import Path

import pytest

from lib import sample_cookbook_snippets
from lib.sample_cookbook_snippets import load_content_fetcher, order_predictions, sample_rows
from lib.snippet_data import write_jsonl


def test_sample_cookbook_snippets_filters_confidence_and_family(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": "GDL-1975-04-18-a-i0119",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 6,
                        "rOffset": 9,
                        "confidence_ner": 0.551,
                    },
                    {
                        "fine_grained_type": "org.ent.pressagency.afp",
                        "surface": "AFP",
                        "lOffset": 14,
                        "rOffset": 17,
                        "confidence_ner": 0.2,
                    },
                    {
                        "fine_grained_type": "org.ent.radiostation.rts",
                        "surface": "RTS",
                        "lOffset": 22,
                        "rOffset": 25,
                        "confidence_ner": 0.5,
                    },
                ],
            },
            {
                "ci_id": "GDL-1975-04-18-a-i0144",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.afp",
                        "surface": "AFP",
                        "lOffset": 6,
                        "rOffset": 9,
                        "confidence_ner": 0.9,
                    }
                ],
            },
        ],
    )

    rows, rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=0,
        max_fetch_failures=25,
        existing_paths=[],
        fetch_content=lambda _ci_id: "Text: ATS then AFP then RTS.",
    )

    assert [row["sample_document_id"] for row in rows] == ["GDL-1975-04-18-a-i0119"]
    assert rows[0]["candidate_label"] == "org.ent.pressagency.ats-sda"
    assert rows[0]["cookbook_prediction"]["confidence"] == 0.551
    assert rejected == []
    assert summary["counts"]["below_min_confidence"] == 1
    assert summary["counts"]["at_or_above_max_confidence"] == 1
    assert summary["counts"]["sampled"] == 1
    assert summary["first_selected"][0]["content_item_url"].endswith("/GDL-1975-04-18-a-i0119")
    assert summary["selected_counts_by_newspaper"] == {"GDL": 1}
    assert summary["selected_counts_by_year"] == {"1975": 1}


def test_sample_cookbook_snippets_keeps_one_prediction_per_content_item(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": "GDL-1975-04-18-a-i0119",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.freie-presse",
                        "surface": "FP",
                        "lOffset": 0,
                        "rOffset": 2,
                        "confidence_ner": 0.52,
                    },
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 8,
                        "rOffset": 11,
                        "confidence_ner": 0.5,
                    },
                ],
            }
        ],
    )

    rows, _rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=12,
        limit=0,
        max_fetch_failures=25,
        existing_paths=[],
        fetch_content=lambda _ci_id: "FP then ATS appears.",
    )

    assert len(rows) == 1
    assert rows[0]["candidate_label"] == "org.ent.pressagency.ats-sda"
    assert summary["counts"]["duplicates_same_content_item"] == 1


def test_sample_cookbook_snippets_preserves_first_seen_document_order(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": "DP-1975-10-30-a-i0007",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 0,
                        "rOffset": 3,
                        "confidence_ner": 0.699,
                    }
                ],
            },
            {
                "ci_id": "BBLT-1877-02-23-a-i0106",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.wolff",
                        "surface": "Wolff",
                        "lOffset": 0,
                        "rOffset": 5,
                        "confidence_ner": 0.454,
                    }
                ],
            },
        ],
    )

    fetched: list[str] = []

    def fetch_content(ci_id: str) -> str:
        fetched.append(ci_id)
        return "ATS" if ci_id.startswith("DP-") else "Wolff"

    sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=1,
        max_fetch_failures=25,
        existing_paths=[],
        fetch_content=fetch_content,
        selection_strategy="input",
        max_per_newspaper=0,
    )

    assert fetched == ["DP-1975-10-30-a-i0007"]


def test_sample_cookbook_snippets_round_robins_newspapers_before_fetch(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": f"HOUR-1875-01-{index + 1:02d}-a-i0001",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.reuters",
                        "surface": "Reuters",
                        "lOffset": 0,
                        "rOffset": 7,
                        "confidence_ner": 0.55,
                    }
                ],
            }
            for index in range(8)
        ]
        + [
            {
                "ci_id": "BBLT-1877-02-23-a-i0106",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.wolff",
                        "surface": "Wolff",
                        "lOffset": 0,
                        "rOffset": 5,
                        "confidence_ner": 0.45,
                    }
                ],
            },
            {
                "ci_id": "NZZ-1794-08-09-a-i0002",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.havas",
                        "surface": "Havas",
                        "lOffset": 0,
                        "rOffset": 5,
                        "confidence_ner": 0.5,
                    }
                ],
            },
        ],
    )

    fetched: list[str] = []

    def fetch_content(ci_id: str) -> str:
        fetched.append(ci_id)
        if ci_id.startswith("HOUR-"):
            return "Reuters dispatch."
        if ci_id.startswith("BBLT-"):
            return "Wolff dispatch."
        return "Havas dispatch."

    rows, _rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=20,
        limit=5,
        max_fetch_failures=25,
        existing_paths=[],
        fetch_content=fetch_content,
        selection_strategy="newspaper-round-robin",
        selection_seed=42,
        max_per_newspaper=0,
    )

    assert len(rows) == 5
    assert Counter(ci_id.split("-", 1)[0] for ci_id in fetched[:3]) == {"BBLT": 1, "HOUR": 1, "NZZ": 1}
    assert Counter(row["newspaper"] for row in rows)["HOUR"] <= 3
    assert summary["settings"]["selection_strategy"] == "newspaper-round-robin"
    assert summary["settings"]["selection_seed"] == 42
    assert summary["settings"]["max_per_newspaper"] == 0


def test_order_predictions_can_cap_each_newspaper() -> None:
    predictions = [
        {
            "ci_id": f"HOUR-1875-01-{index + 1:02d}-a-i0001",
            "label": "org.ent.pressagency.reuters",
            "surface": "Reuters",
            "start": 0,
            "stop": 7,
            "confidence": 0.55,
        }
        for index in range(5)
    ] + [
        {
            "ci_id": f"BBLT-1877-02-{index + 1:02d}-a-i0001",
            "label": "org.ent.pressagency.wolff",
            "surface": "Wolff",
            "start": 0,
            "stop": 5,
            "confidence": 0.45,
        }
        for index in range(2)
    ]

    ordered = order_predictions(
        predictions,
        strategy="newspaper-round-robin",
        seed=7,
        max_per_newspaper=2,
    )

    assert len(ordered) == 4
    assert Counter(prediction["ci_id"].split("-", 1)[0] for prediction in ordered) == {"BBLT": 2, "HOUR": 2}


def test_sample_cookbook_snippets_suppresses_existing_content_items(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    existing_path = tmp_path / "train.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": "GDL-1975-04-18-a-i0119",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 6,
                        "rOffset": 9,
                        "confidence_ner": 0.551,
                    }
                ],
            }
        ],
    )
    write_jsonl(existing_path, [{"document_id": "GDL-1975-04-18-a-i0119"}])

    rows, _rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=0,
        max_fetch_failures=25,
        existing_paths=[existing_path],
        fetch_content=lambda _ci_id: "Text: ATS.",
    )

    assert rows == []
    assert summary["counts"]["existing_content_item"] == 1


def test_sample_cookbook_snippets_rejects_offset_mismatch(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": "GDL-1975-04-18-a-i0119",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 6,
                        "rOffset": 9,
                        "confidence_ner": 0.551,
                    }
                ],
            }
        ],
    )

    rows, rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=0,
        max_fetch_failures=25,
        existing_paths=[],
        fetch_content=lambda _ci_id: "No matching surface here.",
    )

    assert rows == []
    assert rejected[0]["reason"] == "offset_mismatch"
    assert summary["counts"]["offset_mismatch"] == 1


def test_sample_cookbook_snippets_reads_bz2_input(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl.bz2"
    payload = {
        "ci_id": "GDL-1975-04-18-a-i0119",
        "nes": [
            {
                "fine_grained_type": "org.ent.pressagency.ats-sda",
                "surface": "ATS",
                "lOffset": 6,
                "rOffset": 9,
                "confidence_ner": 0.551,
            }
        ],
    }
    with bz2.open(input_path, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")

    rows, _rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=0,
        max_fetch_failures=25,
        existing_paths=[],
        fetch_content=lambda _ci_id: "Text: ATS.",
    )

    assert len(rows) == 1
    assert summary["counts"]["sampled"] == 1


def test_sample_cookbook_snippets_stops_after_fetch_failures(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": f"GDL-1975-04-18-a-i{index:04d}",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 6,
                        "rOffset": 9,
                        "confidence_ner": 0.551,
                    }
                ],
            }
            for index in range(3)
        ],
    )

    def fetch_content(_ci_id: str) -> str:
        raise RuntimeError("500 server error")

    rows, rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=0,
        max_fetch_failures=2,
        existing_paths=[],
        fetch_content=fetch_content,
    )

    assert rows == []
    assert len(rejected) == 2
    assert summary["counts"]["content_fetch_failed"] == 2
    assert summary["counts"]["max_fetch_failures_reached"] == 1


def test_sample_cookbook_snippets_does_not_count_404_as_fetch_failure(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": f"GDL-1975-04-18-a-i{index:04d}",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 6,
                        "rOffset": 9,
                        "confidence_ner": 0.551,
                    }
                ],
            }
            for index in range(3)
        ],
    )

    rows, rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=0,
        max_fetch_failures=1,
        existing_paths=[],
        fetch_content=lambda _ci_id: (_ for _ in ()).throw(RuntimeError("404 not found")),
    )

    assert rows == []
    assert len(rejected) == 3
    assert summary["counts"]["content_item_not_found"] == 1
    assert summary["counts"]["ignored_unavailable_newspaper"] == 2
    assert "content_fetch_failed" not in summary["counts"]
    assert "max_fetch_failures_reached" not in summary["counts"]
    assert summary["ignored_newspapers"][0]["newspaper"] == "GDL"


def test_sample_cookbook_snippets_aborts_when_no_smoke_ids_exist(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": f"GDL-1975-04-18-a-i{index:04d}",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 6,
                        "rOffset": 9,
                        "confidence_ner": 0.551,
                    }
                ],
            }
            for index in range(3)
        ],
    )

    with pytest.raises(RuntimeError, match="API/corpus mismatch"):
        sample_rows(
            input_path,
            family="pressagency",
            min_confidence=0.3,
            max_confidence=0.8,
            context_chars=10,
            limit=0,
            max_fetch_failures=25,
            existing_paths=[],
            fetch_content=lambda _ci_id: (_ for _ in ()).throw(RuntimeError("404 not found")),
            impresso_api_url="https://dev.impresso-project.ch/public-api/v1",
            smoke_content_items=2,
        )


def test_sample_cookbook_snippets_healthcheck_and_smoke_record_endpoint_and_reuse_content(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": "DP-1975-10-30-a-i0007",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 0,
                        "rOffset": 3,
                        "confidence_ner": 0.699,
                    }
                ],
            }
        ],
    )
    fetched: list[str] = []

    def fetch_content(ci_id: str) -> str:
        fetched.append(ci_id)
        return "Known good text." if ci_id == "NZZ-1794-08-09-a-i0002" else "ATS opens this text."

    rows, _rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=0,
        max_fetch_failures=25,
        existing_paths=[],
        fetch_content=fetch_content,
        impresso_api_url="https://dev.impresso-project.ch/public-api/v1",
        api_version={"version": "3.4.0"},
        healthcheck_content_item="NZZ-1794-08-09-a-i0002",
        smoke_content_items=5,
    )

    assert len(rows) == 1
    assert fetched == ["NZZ-1794-08-09-a-i0002", "DP-1975-10-30-a-i0007"]
    assert summary["impresso_api_url"] == "https://dev.impresso-project.ch/public-api/v1"
    assert summary["impresso_api_version"] == {"version": "3.4.0"}
    assert summary["content_items_attempted"] == 2
    assert summary["content_items_retrieved"] == 2
    assert summary["preflight_results"] == [
        {"ci_id": "NZZ-1794-08-09-a-i0002", "kind": "healthcheck", "status": "ok", "text_chars": 16},
        {"ci_id": "DP-1975-10-30-a-i0007", "kind": "cookbook_smoke", "status": "ok", "text_chars": 20},
    ]


def test_sample_cookbook_snippets_fails_on_auth_error(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": "DP-1975-10-30-a-i0007",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 0,
                        "rOffset": 3,
                        "confidence_ner": 0.699,
                    }
                ],
            }
        ],
    )

    with pytest.raises(RuntimeError, match="Impresso authentication failed"):
        sample_rows(
            input_path,
            family="pressagency",
            min_confidence=0.3,
            max_confidence=0.8,
            context_chars=10,
            limit=0,
            max_fetch_failures=25,
            existing_paths=[],
            fetch_content=lambda _ci_id: (_ for _ in ()).throw(RuntimeError("The provided token is invalid.")),
        )


def test_sample_cookbook_snippets_rejects_empty_transcript(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "ci_id": "DP-1975-10-30-a-i0007",
                "nes": [
                    {
                        "fine_grained_type": "org.ent.pressagency.ats-sda",
                        "surface": "ATS",
                        "lOffset": 0,
                        "rOffset": 3,
                        "confidence_ner": 0.699,
                    }
                ],
            }
        ],
    )

    rows, rejected, summary = sample_rows(
        input_path,
        family="pressagency",
        min_confidence=0.3,
        max_confidence=0.8,
        context_chars=10,
        limit=0,
        max_fetch_failures=25,
        existing_paths=[],
        fetch_content=lambda _ci_id: "",
    )

    assert rows == []
    assert rejected[0]["reason"] == "empty_transcript"
    assert summary["counts"]["empty_transcript"] == 1


def test_load_content_fetcher_uses_rest_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_http_json_get(url: str, **_kwargs: object) -> dict[str, object]:
        calls.append(url)
        if url.endswith("/version"):
            return {"version": "3.4.0"}
        assert url.endswith("/content-items/DP-1975-10-30-a-i0007")
        return {"text": {"content": "ATS"}}

    monkeypatch.setenv("IMPRESSO_API_TOKEN", "secret-token")
    monkeypatch.setattr(sample_cookbook_snippets, "http_json_get", fake_http_json_get)

    fetch = load_content_fetcher("https://dev.impresso-project.ch/public-api/v1")

    assert fetch("DP-1975-10-30-a-i0007") == "ATS"
    assert getattr(fetch, "api_version") == {"version": "3.4.0"}
    assert calls == [
        "https://dev.impresso-project.ch/public-api/v1/version",
        "https://dev.impresso-project.ch/public-api/v1/content-items/DP-1975-10-30-a-i0007",
    ]
