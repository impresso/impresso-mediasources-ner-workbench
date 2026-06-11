import json
from pathlib import Path

from lib.apply_curation_decisions import apply_curation, parse_args, parse_correction


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def row(doc_id: str, tokens: list[str], labels: list[str]) -> dict:
    text = " ".join(tokens)
    starts = []
    stops = []
    cursor = 0
    for token in tokens:
        starts.append(cursor)
        cursor += len(token)
        stops.append(cursor)
        cursor += 1
    entities = []
    index = 0
    while index < len(labels):
        label = labels[index]
        if label == "O":
            index += 1
            continue
        base = label[2:]
        start = index
        index += 1
        while index < len(labels) and labels[index] == f"I-{base}":
            index += 1
        stop = index
        entities.append(
            {
                "entity_id": f"{doc_id}#ent-{len(entities)}",
                "token_start": start,
                "token_stop": stop,
                "start": starts[start],
                "stop": stops[stop - 1],
                "surface": text[starts[start] : stops[stop - 1]],
                "normalized_surface": text[starts[start] : stops[stop - 1]],
                "label_original": base,
                "label": base,
                "entity_family": "pressagency",
                "nel": "",
                "wikidata_url": None,
                "has_ocr_correction": False,
                "max_ocr_levenshtein": 0.0,
                "status": "accepted",
            }
        )
    return {
        "id": doc_id,
        "split": "validation",
        "language": "fr",
        "newspaper": "JDG",
        "date": "1900-01-01",
        "source_file": "fixture.tsv",
        "text": text,
        "tokens": tokens,
        "token_start_offsets": starts,
        "token_end_offsets": stops,
        "token_labels": labels,
        "token_label_ids": [0] * len(tokens),
        "token_nel": [""] * len(tokens),
        "token_ocr": [""] * len(tokens),
        "token_render": ["_"] * len(tokens),
        "token_segment_ids": [0] * len(tokens),
        "entities": entities,
        "segments": [],
        "sentences": [],
        "quality_flags": [],
        "metadata": {},
    }


def test_parse_correction_span() -> None:
    correction = parse_correction('covered by 13:15 "Agence Wolff" label=org.ent.pressagency.wolff; partial duplicate')

    assert correction is not None
    assert correction.token_start == 13
    assert correction.token_stop == 15
    assert correction.label == "org.ent.pressagency.wolff"


def test_apply_curation_defaults_to_all_dataset_splits() -> None:
    args = parse_args(
        [
            "--input-dir",
            "input",
            "--output-dir",
            "output",
            "--disagreements",
            "disagreements.jsonl",
            "--decisions",
            "decisions.jsonl",
        ]
    )

    assert args.splits == "train validation test"


def test_apply_prediction_correction_adds_entity(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source = row("doc1", ["l", "'", "Agence", "Wolff"], ["O", "O", "O", "O"])
    write_jsonl(input_dir / "validation.jsonl", [source])
    write_jsonl(input_dir / "test.jsonl", [])
    write_jsonl(
        tmp_path / "disagreements.jsonl",
        [
            {
                "review_id": "validation:doc1:abc",
                "split": "validation",
                "document": {"id": "doc1"},
                "gold": None,
                "prediction": {"token_start": 2, "token_stop": 3, "label": "org.ent.pressagency.wolff"},
            }
        ],
    )
    write_jsonl(
        tmp_path / "decisions.jsonl",
        [
            {
                "review_id": "validation:doc1:abc",
                "status": "done",
                "choice": "prediction",
                "correct_label": "org.ent.pressagency.wolff",
                "notes": '2:4 "Agence Wolff" label=org.ent.pressagency.wolff',
                "reviewer": "tester",
                "reviewed_at": "2026-05-31T12:00:00+02:00",
            }
        ],
    )

    apply_curation(
        input_dir=input_dir,
        output_dir=output_dir,
        disagreements_path=tmp_path / "disagreements.jsonl",
        decisions_path=tmp_path / "decisions.jsonl",
        splits=["validation", "test"],
        require_complete=True,
    )

    revised = json.loads((output_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines()[0])
    tsv = (output_dir / "curation_changes_tags.tsv").read_text(encoding="utf-8")
    assert revised["token_labels"] == ["O", "O", "B-org.ent.pressagency.wolff", "I-org.ent.pressagency.wolff"]
    assert revised["entities"][0]["surface"] == "Agence Wolff"
    assert "TOKEN\tBEFORE_NERTAG\tAFTER_NERTAG" in tsv
    assert "Agence\tO\tB-org.ent.pressagency.wolff" in tsv
    assert "Wolff\tO\tI-org.ent.pressagency.wolff" in tsv


def test_apply_neither_without_correction_removes_gold(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source = row("doc1", ["A", ".", "F", ".", "P", "."], ["B-org.ent.pressagency.afp", "I-org.ent.pressagency.afp", "I-org.ent.pressagency.afp", "I-org.ent.pressagency.afp", "I-org.ent.pressagency.afp", "I-org.ent.pressagency.afp"])
    write_jsonl(input_dir / "validation.jsonl", [source])
    write_jsonl(input_dir / "test.jsonl", [])
    write_jsonl(
        tmp_path / "disagreements.jsonl",
        [
            {
                "review_id": "validation:doc1:abc",
                "split": "validation",
                "document": {"id": "doc1"},
                "gold": {"token_start": 0, "token_stop": 6, "label": "org.ent.pressagency.afp"},
                "prediction": {"token_start": 2, "token_stop": 5, "label": "org.ent.pressagency.afp"},
            }
        ],
    )
    write_jsonl(
        tmp_path / "decisions.jsonl",
        [
            {
                "review_id": "validation:doc1:abc",
                "status": "done",
                "choice": "neither",
                "notes": "not a valid mention",
                "reviewer": "tester",
                "reviewed_at": "2026-05-31T12:00:00+02:00",
            }
        ],
    )

    apply_curation(
        input_dir=input_dir,
        output_dir=output_dir,
        disagreements_path=tmp_path / "disagreements.jsonl",
        decisions_path=tmp_path / "decisions.jsonl",
        splits=["validation", "test"],
        require_complete=True,
    )

    revised = json.loads((output_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert revised["token_labels"] == ["O", "O", "O", "O", "O", "O"]
    assert revised["entities"] == []


def test_apply_empty_prediction_removes_gold(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source = row("doc1", ["SDA"], ["B-org.ent.pressagency.ats-sda"])
    write_jsonl(input_dir / "validation.jsonl", [source])
    write_jsonl(input_dir / "test.jsonl", [])
    write_jsonl(
        tmp_path / "disagreements.jsonl",
        [
            {
                "review_id": "validation:doc1:abc",
                "split": "validation",
                "document": {"id": "doc1"},
                "gold": {"token_start": 0, "token_stop": 1, "label": "org.ent.pressagency.ats-sda"},
                "prediction": None,
            }
        ],
    )
    write_jsonl(
        tmp_path / "decisions.jsonl",
        [
            {
                "review_id": "validation:doc1:abc",
                "status": "done",
                "choice": "prediction",
                "correct_label": "",
                "reviewer": "tester",
                "reviewed_at": "2026-05-31T12:00:00+02:00",
            }
        ],
    )

    apply_curation(
        input_dir=input_dir,
        output_dir=output_dir,
        disagreements_path=tmp_path / "disagreements.jsonl",
        decisions_path=tmp_path / "decisions.jsonl",
        splits=["validation", "test"],
        require_complete=True,
    )

    revised = json.loads((output_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines()[0])
    changes = json.loads((output_dir / "curation_changes.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert revised["token_labels"] == ["O"]
    assert revised["entities"] == []
    assert changes["action"] == "accepted_empty_prediction"


def test_apply_ignored_skip_leaves_row_unchanged(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source = row("doc1", ["Havas"], ["O"])
    write_jsonl(input_dir / "validation.jsonl", [source])
    write_jsonl(input_dir / "test.jsonl", [])
    write_jsonl(
        tmp_path / "disagreements.jsonl",
        [
            {
                "review_id": "validation:doc1:abc",
                "split": "validation",
                "document": {"id": "doc1"},
                "gold": None,
                "prediction": {"token_start": 0, "token_stop": 1, "label": "org.ent.pressagency.havas"},
            }
        ],
    )
    write_jsonl(
        tmp_path / "decisions.jsonl",
        [
            {
                "review_id": "validation:doc1:abc",
                "status": "ignored",
                "choice": "skip",
                "reviewer": "tester",
                "reviewed_at": "2026-05-31T12:00:00+02:00",
            }
        ],
    )

    apply_curation(
        input_dir=input_dir,
        output_dir=output_dir,
        disagreements_path=tmp_path / "disagreements.jsonl",
        decisions_path=tmp_path / "decisions.jsonl",
        splits=["validation", "test"],
        require_complete=True,
    )

    revised = json.loads((output_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines()[0])
    changes = json.loads((output_dir / "curation_changes.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert revised["token_labels"] == ["O"]
    assert revised["entities"] == []
    assert changes["action"] == "ignored"
