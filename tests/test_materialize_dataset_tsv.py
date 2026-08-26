import json
from pathlib import Path

import pytest

from lib.materialize_dataset_tsv import materialize


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_materialize_dataset_tsv_writes_doc_boundaries(tmp_path: Path) -> None:
    input_path = tmp_path / "train.jsonl"
    output_path = tmp_path / "tsv" / "train.tsv"
    write_jsonl(
        input_path,
        [
            {
                "id": "row-b",
                "document_id": "doc-b",
                "tokens": ["BBC"],
                "token_labels": ["B-org.ent.radiostation.bbc"],
            },
            {
                "id": "row-a",
                "document_id": "doc-a",
                "split": "train",
                "language": "fr",
                "newspaper": "EXP",
                "date": "1950-01-01",
                "tokens": ["Agence", "Radio"],
                "token_labels": ["B-org.ent.pressagency.agence-radio", "I-org.ent.pressagency.agence-radio"],
            },
        ],
    )

    summary = materialize(input_path, output_path, split="train")

    assert summary["rows"] == 2
    assert output_path.read_text(encoding="utf-8").splitlines() == [
        "# doc_id = row-a",
        "# document_id = doc-a",
        "# split = train",
        "# language = fr",
        "# newspaper = EXP",
        "# date = 1950-01-01",
        "TOKEN\tNERTAG",
        "Agence\tB-org.ent.pressagency.agence-radio",
        "Radio\tI-org.ent.pressagency.agence-radio",
        "",
        "# doc_id = row-b",
        "# document_id = doc-b",
        "# split = train",
        "TOKEN\tNERTAG",
        "BBC\tB-org.ent.radiostation.bbc",
        "",
    ]


def test_materialize_dataset_tsv_rejects_misaligned_labels(tmp_path: Path) -> None:
    input_path = tmp_path / "test.jsonl"
    output_path = tmp_path / "test.tsv"
    write_jsonl(input_path, [{"id": "doc-1", "tokens": ["AFP"], "token_labels": []}])

    with pytest.raises(ValueError, match="tokens/token_labels length mismatch"):
        materialize(input_path, output_path, split="test")
