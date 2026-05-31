from lib.build_curation_review import build_disagreements, summarize


def test_build_disagreements_groups_overlap_and_extra_prediction() -> None:
    source_rows = [
        {
            "id": "doc1",
            "language": "de",
            "newspaper": "DTT",
            "date": "1945-01-01",
            "source_file": "fixture.tsv",
            "tokens": ["foo", "Agence", "Havas", "bar", "Reuters"],
            "token_start_offsets": [0, 4, 11, 17, 21],
            "token_end_offsets": [3, 10, 16, 20, 28],
        }
    ]
    prediction_rows = [
        {
            "id": "doc1",
            "gold_labels": ["O", "B-org.ent.pressagency.havas", "I-org.ent.pressagency.havas", "O", "O"],
            "pred_labels": ["O", "B-org.ent.pressagency.afp", "I-org.ent.pressagency.afp", "O", "B-org.ent.pressagency.reuters"],
        }
    ]

    rows = build_disagreements(
        "validation",
        source_rows,
        prediction_rows,
        languages={"de", "fr"},
        context_radius=1,
    )

    assert [row["issue_type"] for row in rows] == ["label_mismatch", "extra_prediction"]
    assert rows[0]["gold"]["label"] == "org.ent.pressagency.havas"
    assert rows[0]["prediction"]["label"] == "org.ent.pressagency.afp"
    assert rows[1]["prediction"]["surface"] == "Reuters"
    assert summarize(rows)["by_language"] == {"de": 2}


def test_build_disagreements_filters_languages() -> None:
    source_rows = [{"id": "doc1", "language": "lb", "tokens": ["Havas"]}]
    prediction_rows = [{"id": "doc1", "gold_labels": ["B-org.ent.pressagency.havas"], "pred_labels": ["O"]}]

    rows = build_disagreements(
        "test",
        source_rows,
        prediction_rows,
        languages={"de", "fr"},
        context_radius=1,
    )

    assert rows == []
