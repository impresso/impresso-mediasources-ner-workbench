import json
from pathlib import Path

from lib.review_tsv_search import review_hits, token_index_for_line, tsv_hit


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_tsv_hit_maps_line_hit_to_document_token_offsets() -> None:
    lines = [
        "# doc_id = doc-1\n",
        "# document_id = doc-1\n",
        "# split = train\n",
        "TOKEN\tNERTAG\n",
        "Die\tO\n",
        "BBC\tO\n",
    ]

    assert token_index_for_line(lines, (5, 6), 5) == 1
    hit = tsv_hit(lines, (5, 6))
    assert hit.document_id == "doc-1"
    assert (hit.token_start, hit.token_stop) == (1, 2)


def test_review_tsv_search_accepts_default_hit_and_label(tmp_path: Path, monkeypatch) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    tsv = tmp_path / "train.tsv"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    metadata = tmp_path / "labels.json"
    summary = tmp_path / "summary.json"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "Die BBC",
                "tokens": ["Die", "BBC"],
                "token_start_offsets": [0, 4],
                "token_end_offsets": [3, 7],
                "token_labels": ["O", "O"],
                "entities": [],
            }
        ],
    )
    tsv.write_text(
        "# doc_id = doc-1\n"
        "# document_id = doc-1\n"
        "# split = train\n"
        "TOKEN\tNERTAG\n"
        "Die\tO\n"
        "BBC\tO\n",
        encoding="utf-8",
    )
    metadata.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "bbc",
                    "label": "org.ent.radiostation.bbc",
                }
            ]
        ),
        encoding="utf-8",
    )
    answers = iter(["a", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    result = review_hits(
        input_jsonl=input_jsonl,
        tsv_path=tsv,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="org.ent.radiostation.bbc",
        reviewer="tester",
        token="BBC",
        label_metadata_paths=[metadata],
        summary_json=summary,
    )

    assert result["hits"] == 1
    assert result["accepted"] == 1
    candidate = json.loads(candidates.read_text(encoding="utf-8").splitlines()[0])
    decision = json.loads(decisions.read_text(encoding="utf-8").splitlines()[0])
    assert candidate["document_id"] == "doc-1"
    assert candidate["predicted_entities"][0]["token_start"] == 1
    assert candidate["predicted_entities"][0]["token_stop"] == 2
    assert decision["audit_status"] == "verified"
    assert decision["choice"] == "accept"
