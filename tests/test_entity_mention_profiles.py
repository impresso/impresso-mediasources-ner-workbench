import json
from pathlib import Path

from lib.entity_mention_profiles import build_profiles


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_build_profiles_counts_surfaces_and_generic_terms(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "havas",
                    "display_name": "Havas",
                    "label": "org.ent.pressagency.havas",
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        source,
        [
            {
                "document_id": "doc-1",
                "language": "fr",
                "text": "Agence Havas Havas",
                "entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "start": 0,
                        "stop": 12,
                        "surface": "Agence Havas",
                    },
                    {
                        "label": "org.ent.pressagency.havas",
                        "start": 13,
                        "stop": 18,
                        "surface": "Havas",
                    },
                ],
            },
            {
                "document_id": "doc-2",
                "language": "de",
                "text": "Agence Havas",
                "entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "start": 0,
                        "stop": 12,
                        "surface": "Agence Havas",
                    }
                ],
            },
        ],
    )
    args = type(
        "Args",
        (),
        {
            "input_jsonl": [f"train={source}"],
            "label_metadata": [metadata],
            "top_n": 10,
        },
    )()

    report = build_profiles(args)

    profile = report["profiles"][0]
    assert profile["label"] == "org.ent.pressagency.havas"
    assert profile["total"] == 3
    assert profile["languages"] == {"de": 1, "fr": 2}
    assert profile["top_surfaces"][0]["surface"] == "Agence Havas"
    assert profile["top_surfaces"][0]["count"] == 2
    assert profile["top_surfaces"][0]["generic_terms"] == ["agence"]
