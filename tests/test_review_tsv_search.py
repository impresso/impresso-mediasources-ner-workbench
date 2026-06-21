import json
from pathlib import Path

from lib.review_tsv_search import nearest_token_sequence, review_hits, token_index_for_line, tokens_from_tsv_lines, tsv_hit, visible_token_bounds


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


def test_tsv_annotation_lines_resolve_to_nearest_document_match() -> None:
    row = {"id": "doc-1", "tokens": ["BBC", "und", "Voice", "of", "America", "und", "die", "BBC"]}

    assert tokens_from_tsv_lines(["\x1b[31;1mBBC\x1b[0m\tO"]) == ["BBC"]
    assert nearest_token_sequence(row, ["BBC"], (7, 8)) == (7, 8)
    assert nearest_token_sequence(row, ["BBC"], (7, 8), bounds=(5, 8)) == (7, 8)
    assert nearest_token_sequence(row, ["Voice", "of", "America"], (4, 5)) == (2, 5)


def test_visible_token_bounds_follow_displayed_context() -> None:
    lines = [
        "# doc_id = doc-1\n",
        "# document_id = doc-1\n",
        "# split = train\n",
        "TOKEN\tNERTAG\n",
        "a\tO\n",
        "b\tO\n",
        "c\tO\n",
        "d\tO\n",
        "e\tO\n",
    ]

    assert visible_token_bounds(lines, (6, 7), context=1) == (1, 4)


def test_review_tsv_search_accepts_pasted_tsv_line_and_default_label(tmp_path: Path, monkeypatch) -> None:
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
    answers = iter(["a", "BBC\tO", "", ""])
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


def test_review_tsv_search_accepts_pasted_span_larger_than_hit(tmp_path: Path, monkeypatch) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    tsv = tmp_path / "train.tsv"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    metadata = tmp_path / "labels.json"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "Die Voice of America",
                "tokens": ["Die", "Voice", "of", "America"],
                "token_start_offsets": [0, 4, 10, 13],
                "token_end_offsets": [3, 9, 12, 20],
                "token_labels": ["O", "O", "O", "O"],
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
        "Voice\tO\n"
        "of\tO\n"
        "America\tO\n",
        encoding="utf-8",
    )
    metadata.write_text(json.dumps([{"canonical_id": "voa", "label": "org.ent.radiostation.voa"}]), encoding="utf-8")
    answers = iter(["a", "Voice\tO", "of\tO", "America\tO", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    result = review_hits(
        input_jsonl=input_jsonl,
        tsv_path=tsv,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="org.ent.radiostation.voa",
        reviewer="tester",
        token="America",
        label_metadata_paths=[metadata],
    )

    assert result["accepted"] == 1
    candidate = json.loads(candidates.read_text(encoding="utf-8").splitlines()[0])
    assert candidate["predicted_entities"][0]["surface"] == "Voice of America"
    assert candidate["predicted_entities"][0]["token_start"] == 1
    assert candidate["predicted_entities"][0]["token_stop"] == 4


def test_review_tsv_search_marks_highlighted_hit_as_true_o(tmp_path: Path, monkeypatch) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    tsv = tmp_path / "train.tsv"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
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
    answers = iter(["v"])
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
    )

    assert result["accepted"] == 1
    candidate = json.loads(candidates.read_text(encoding="utf-8").splitlines()[0])
    decision = json.loads(decisions.read_text(encoding="utf-8").splitlines()[0])
    assert candidate["audit_mode"] == "manual-tsv-remove"
    assert candidate["target_label"] == "O"
    assert candidate["predicted_entities"][0]["label"] == "O"
    assert decision["correct_label"] == "O"
    assert decision["audit_status"] == "verified"
