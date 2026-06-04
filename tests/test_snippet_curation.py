import json
from pathlib import Path

from lib.build_newsagency_snippets import build_snippets
from lib.export_snippet_training_data import export_rows
from lib.review_newsagency_snippets import parse_manual_span, prompt_manual_spans, review_loop
from lib.review_radiostation_snippets import materialize_views
from lib.sample_newsagencies import extract_candidate, load_seed_queries
from lib.score_radiostation_snippets import find_alias_spans, score_rows as score_radiostation_rows
from lib.score_newsagency_snippets import (
    attach_surfaces,
    curation_status,
    normalize_dotted_acronym_spans,
    suppress_contained_same_label_spans,
)
from lib.snippet_data import tokenize_with_offsets, write_jsonl


def test_tokenize_with_offsets_keeps_character_spans() -> None:
    text = "Selon l'Agence Havas."

    tokens, starts, stops = tokenize_with_offsets(text)

    assert tokens == ["Selon", "l'Agence", "Havas", "."]
    assert [text[start:stop] for start, stop in zip(starts, stops, strict=True)] == tokens


def test_newsagency_curation_status_auto_accepts_matching_confident_span() -> None:
    row = {"candidate_label": "org.ent.pressagency.havas"}
    spans = [
        {
            "token_start": 2,
            "token_stop": 3,
            "label": "org.ent.pressagency.havas",
            "surface": "Havas",
            "confidence": 0.99,
            "margin": 0.50,
        }
    ]

    assert curation_status(row, spans, min_confidence=0.95, min_margin=0.30) == ("auto_accepted", [])


def test_newsagency_curation_status_auto_accepts_multiple_very_confident_spans() -> None:
    row = {"candidate_label": "org.ent.pressagency.up-upi"}
    spans = [
        {
            "token_start": 9,
            "token_stop": 10,
            "label": "org.ent.pressagency.afp",
            "surface": "AFP",
            "confidence": 0.999,
            "margin": 0.995,
        },
        {
            "token_start": 24,
            "token_stop": 26,
            "label": "org.ent.pressagency.up-upi",
            "surface": "United Press",
            "confidence": 0.999,
            "margin": 0.995,
        },
    ]

    assert curation_status(row, spans, min_confidence=0.99, min_margin=0.30, multiple_min_confidence=0.99) == (
        "auto_accepted",
        [],
    )


def test_normalize_dotted_acronym_spans_includes_final_abbreviation_period() -> None:
    text = "PARIS, 11 (A. F. P.)."
    tokens = ["PARIS", ",", "11", "(", "A", ".", "F", ".", "P", ".", ")", "."]
    starts = [0, 5, 7, 10, 11, 12, 14, 15, 17, 18, 19, 20]
    stops = [5, 6, 9, 11, 12, 13, 15, 16, 18, 19, 20, 21]
    raw_spans = [
        {"token_start": 4, "token_stop": 9, "label": "org.ent.pressagency.afp", "confidence": 1.0, "margin": 1.0},
        {"token_start": 4, "token_stop": 7, "label": "org.ent.pressagency.afp", "confidence": 0.5, "margin": 0.1},
        {"token_start": 8, "token_stop": 9, "label": "org.ent.pressagency.afp", "confidence": 0.8, "margin": 0.6},
    ]

    spans = normalize_dotted_acronym_spans(attach_surfaces(raw_spans, tokens, starts, stops, text), tokens, starts, stops, text)

    assert len(spans) == 1
    assert spans[0]["token_start"] == 4
    assert spans[0]["token_stop"] == 10
    assert spans[0]["surface"] == "A. F. P."
    assert spans[0]["boundary_normalization"] == "include_final_dotted_acronym_period"


def test_normalize_dotted_acronym_spans_does_not_include_sentence_period_after_plain_acronym() -> None:
    text = "La depêche vient de AFP."
    tokens = ["La", "depêche", "vient", "de", "AFP", "."]
    starts = [0, 3, 11, 17, 20, 23]
    stops = [2, 10, 16, 19, 23, 24]
    raw_spans = [
        {"token_start": 4, "token_stop": 5, "label": "org.ent.pressagency.afp", "confidence": 1.0, "margin": 1.0}
    ]

    spans = normalize_dotted_acronym_spans(attach_surfaces(raw_spans, tokens, starts, stops, text), tokens, starts, stops, text)

    assert spans[0]["token_stop"] == 5
    assert spans[0]["surface"] == "AFP"


def test_normalize_dotted_acronym_spans_drops_punctuation_only_predictions() -> None:
    text = "A. F. P."
    tokens = ["A", ".", "F", ".", "P", "."]
    starts = [0, 1, 3, 4, 6, 7]
    stops = [1, 2, 4, 5, 7, 8]
    raw_spans = [
        {"token_start": 5, "token_stop": 6, "label": "org.ent.pressagency.up-upi", "confidence": 0.8, "margin": 0.6}
    ]

    spans = normalize_dotted_acronym_spans(attach_surfaces(raw_spans, tokens, starts, stops, text), tokens, starts, stops, text)

    assert spans == []


def test_alias_matcher_keeps_final_period_for_dotted_acronym_alias() -> None:
    tokens = ["(", "A", ".", "F", ".", "P", ".", ")", "."]

    spans = find_alias_spans(tokens, ["A.F.P."], "org.ent.pressagency.afp")

    assert spans == [
        {
            "token_start": 1,
            "token_stop": 7,
            "label": "org.ent.pressagency.afp",
            "surface": "A . F . P .",
            "confidence": 1.0,
            "margin": 1.0,
            "matcher": "alias_compact",
            "alias": "A.F.P.",
        }
    ]


def test_alias_matcher_keeps_final_period_for_dotted_ats_alias() -> None:
    tokens = ["MOSCOU", ",", "7", "(", "A", ".", "T", ".", "S", ".", ")", "."]

    spans = find_alias_spans(tokens, ["A.T.S."], "org.ent.pressagency.ats-sda")

    assert spans == [
        {
            "token_start": 4,
            "token_stop": 10,
            "label": "org.ent.pressagency.ats-sda",
            "surface": "A . T . S .",
            "confidence": 1.0,
            "margin": 1.0,
            "matcher": "alias_compact",
            "alias": "A.T.S.",
        }
    ]


def test_suppress_contained_same_label_spans_keeps_full_acronym_span() -> None:
    spans = [
        {"token_start": 19, "token_stop": 25, "label": "org.ent.pressagency.afp", "surface": "A. F. P."},
        {"token_start": 19, "token_stop": 23, "label": "org.ent.pressagency.afp", "surface": "A. F."},
        {"token_start": 23, "token_stop": 24, "label": "org.ent.pressagency.afp", "surface": "P"},
    ]

    assert suppress_contained_same_label_spans(spans) == [spans[0]]


def test_sample_newsagencies_loads_label_alias_queries(tmp_path: Path) -> None:
    seeds = tmp_path / "newsagency_seeds.json"
    seeds.write_text(
        json.dumps(
            [
                {
                    "label": "org.ent.pressagency.reuters",
                    "canonical_id": "reuters",
                    "display_name": "Reuters",
                    "aliases": ["Reuters"],
                    "aliases_by_language": {"de": ["Reuter"], "fr": ["Agence Reuters"]},
                    "trainable": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    queries = load_seed_queries(seeds, languages=["de", "fr"], labels=None, max_queries_per_label=0)

    assert {query["query"] for query in queries} == {"Reuters", "Reuter", "Agence Reuters"}
    assert {query["label"] for query in queries} == {"org.ent.pressagency.reuters"}


def test_sample_newsagencies_extracts_search_candidate() -> None:
    row = extract_candidate(
        {
            "id": "DTT-1959-12-01-a-i0079",
            "text": {
                "langCode": "de",
                "snippet": "Die Agentur Reuter meldet.",
                "matches": [{"fragment": "Die Agentur <em>Reuter</em> meldet."}],
            },
            "meta": {
                "date": "1959-12-01T00:00:00+00:00",
                "mediaId": "DTT",
                "mediaTitle": "Tageblatt",
                "page_id": "DTT-1959-12-01-a-p0001",
            },
        },
        query={
            "query": "Reuter",
            "label": "org.ent.pressagency.reuters",
            "canonical_id": "reuters",
            "display_name": "Reuters",
        },
        search_language="de",
        require_matches=True,
    )

    assert row is not None
    assert row["candidate_label"] == "org.ent.pressagency.reuters"
    assert row["query"] == "Reuter"
    assert row["snippet"] == "Die Agentur Reuter meldet."
    assert row["matches"] == ["Die Agentur <em>Reuter</em> meldet."]
    assert row["source"] == {"type": "impresso_search_result", "document_id": "DTT-1959-12-01-a-i0079"}


def test_build_newsagency_snippets_from_legacy_jsonl(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    write_jsonl(
        source,
        [
            {
                "id": "doc-1",
                "split": "train",
                "language": "fr",
                "date": "1946-01-01",
                "newspaper": "JDG",
                "text": "Selon Agence Havas, la nouvelle arrive.",
                "tokens": ["Selon", "Agence", "Havas", ",", "la", "nouvelle", "arrive", "."],
                "token_start_offsets": [0, 6, 13, 18, 20, 23, 32, 38],
                "token_end_offsets": [5, 12, 18, 19, 22, 31, 38, 39],
                "entities": [
                    {
                        "token_start": 1,
                        "token_stop": 3,
                        "label": "org.ent.pressagency.havas",
                        "surface": "Agence Havas",
                    }
                ],
            }
        ],
    )

    rows = build_snippets([source], radius=1, labels=None, limit=0)

    assert rows[0]["id"] == "doc-1#snippet-1-3"
    assert rows[0]["candidate_label"] == "org.ent.pressagency.havas"
    assert rows[0]["tokens"] == ["Selon", "Agence", "Havas", ","]
    assert rows[0]["seed_span"] == {
        "label": "org.ent.pressagency.havas",
        "surface": "Agence Havas",
        "token_start": 1,
        "token_stop": 3,
    }


def test_export_snippet_training_data_writes_training_rows(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    label_map_path.write_text(
        json.dumps(
            {
                "label2id": {
                    "O": 0,
                    "B-org.ent.pressagency.havas": 1,
                    "I-org.ent.pressagency.havas": 2,
                },
                "id2label": {
                    "0": "O",
                    "1": "B-org.ent.pressagency.havas",
                    "2": "I-org.ent.pressagency.havas",
                },
            }
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "snippet-1",
                "snippet": "Selon Havas.",
                "language": "fr",
                "date": "1946-01-01",
                "candidate_label": "org.ent.pressagency.havas",
                "curation": {"status": "accepted", "label": "org.ent.pressagency.havas"},
                "accepted_spans": [
                    {
                        "token_start": 1,
                        "token_stop": 2,
                        "label": "org.ent.pressagency.havas",
                    }
                ],
            }
        ],
    )

    rows = export_rows(input_path, label_map_path)

    assert len(rows) == 1
    assert rows[0]["tokens"] == ["Selon", "Havas", "."]
    assert rows[0]["token_labels"] == ["O", "B-org.ent.pressagency.havas", "O"]
    assert rows[0]["entities"][0]["surface"] == "Havas"
    assert rows[0]["source_component"] == "newsagency_snippet_manual"


def test_radiostation_alias_scoring_and_export(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    reviewed_path = tmp_path / "radio_reviewed.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    label_map_path = tmp_path / "label_map.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "bbc",
                    "label": "org.ent.radiostation.bbc",
                    "display_name": "BBC",
                    "aliases": ["BBC", "B. B. C."],
                }
            ]
        ),
        encoding="utf-8",
    )
    label_map_path.write_text(json.dumps({"label2id": {"O": 0}, "id2label": {"0": "O"}}), encoding="utf-8")
    write_jsonl(
        input_path,
        [
            {
                "id": "radio-1",
                "label": "org.ent.radiostation",
                "station": "bbc",
                "query": "BBC",
                "search_language": "fr",
                "language": "fr",
                "snippet": "Relais de la BBC.",
                "matches": ["Relais de la <em>BBC</em>."],
            }
        ],
    )

    result = score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )
    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    scored["curation"]["status"] = "accepted"
    scored["accepted_spans"] = scored["model"]["predicted_spans"]
    write_jsonl(reviewed_path, [scored])

    rows = export_rows(reviewed_path, label_map_path, extra_label_metadata=[seeds_path])

    assert result["rows"] == 1
    assert scored["model"]["predicted_spans"][0]["surface"] == "BBC"
    assert rows[0]["token_labels"] == ["O", "O", "O", "B-org.ent.radiostation.bbc", "O"]
    assert rows[0]["entities"][0]["entity_family"] == "radiostation"
    assert rows[0]["source_component"] == "radiostation_snippet_manual"


def test_radiostation_scoring_resolves_query_alias_to_canonical_label(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "bbc",
                    "label": "org.ent.radiostation.bbc",
                    "display_name": "BBC",
                    "aliases": ["BBC", "Radio Londres", "Radio London"],
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "radio-londres-1",
                "label": "org.ent.radiostation",
                "station": "radio_londres",
                "query": "Radio Londres",
                "language": "fr",
                "snippet": "Radio Londres diffuse un appel.",
            }
        ],
    )

    score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    assert scored["candidate_label"] == "org.ent.radiostation.bbc"
    assert scored["curation"]["label"] == "org.ent.radiostation.bbc"
    assert scored["model"]["predicted_spans"][0]["label"] == "org.ent.radiostation.bbc"
    assert scored["model"]["predicted_spans"][0]["surface"] == "Radio Londres"


def test_radiostation_scoring_matches_other_station_aliases_in_snippet(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "bbc",
                    "label": "org.ent.radiostation.bbc",
                    "display_name": "BBC",
                    "aliases": ["BBC", "Radio Londres"],
                },
                {
                    "canonical_id": "radio-moscow",
                    "label": "org.ent.radiostation.radio-moscow",
                    "display_name": "Radio Moscow",
                    "aliases": ["Radio Moscow", "Radio Moscou"],
                },
                {
                    "canonical_id": "radio-bucharest",
                    "label": "org.ent.radiostation.radio-bucharest",
                    "display_name": "Radio Bucharest",
                    "aliases": ["Radio Bucharest", "Radio Bucarest"],
                },
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "radio-londres-with-moscow",
                "label": "org.ent.radiostation",
                "station": "radio_londres",
                "query": "Radio Londres",
                "language": "fr",
                "snippet": "Moscou, 9. — Radio-Moscou annonce la protestation.",
            },
            {
                "id": "radio-moscou-with-bucarest",
                "label": "org.ent.radiostation",
                "station": "radio_moscow",
                "query": "Radio Moscou",
                "language": "fr",
                "snippet": "BUCAREST, 9 (Reuter). — Radio-Bucarest annonce la nouvelle.",
            }
        ],
    )

    score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored_rows = [
        json.loads(line)
        for line in scored_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    london_scored = next(row for row in scored_rows if row["id"] == "radio-londres-with-moscow")
    bucharest_scored = next(row for row in scored_rows if row["id"] == "radio-moscou-with-bucarest")

    assert london_scored["candidate_label"] == "org.ent.radiostation.bbc"
    assert any(
        span["surface"] == "Radio-Moscou" and span["label"] == "org.ent.radiostation.radio-moscow"
        for span in london_scored["model"]["predicted_spans"]
    )
    assert any(
        span["surface"] == "Radio-Bucarest" and span["label"] == "org.ent.radiostation.radio-bucharest"
        for span in bucharest_scored["model"]["predicted_spans"]
    )


def test_radiostation_scoring_matches_pressagency_aliases_in_snippet(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    radio_seeds_path = tmp_path / "radiostation_seeds.json"
    agency_seeds_path = tmp_path / "newsagency_seeds.json"
    radio_seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "bbc",
                    "label": "org.ent.radiostation.bbc",
                    "display_name": "BBC",
                    "aliases": ["BBC", "Radio London"],
                }
            ]
        ),
        encoding="utf-8",
    )
    agency_seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "ats-sda",
                    "label": "org.ent.pressagency.ats-sda",
                    "display_name": "Schweizerische Depeschenagentur",
                    "aliases": ["Schweizerische Depeschenagentur", "Schweizer Depeschenagentur", "SDA"],
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "radio-london-with-sda",
                "label": "org.ent.radiostation",
                "station": "radio_londres",
                "query": "Radio London",
                "language": "de",
                "snippet": "Wie die Schweizer Depeschenagentur aus London berichtet, gab Radio London bekannt.",
            }
        ],
    )

    score_radiostation_rows(
        type(
            "Args",
            (),
            {
                "input": str(input_path),
                "output": str(scored_path),
                "radiostations": str(radio_seeds_path),
                "newsagencies": str(agency_seeds_path),
            },
        )
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    spans = scored["model"]["predicted_spans"]
    assert any(
        span["surface"] == "Schweizer Depeschenagentur" and span["label"] == "org.ent.pressagency.ats-sda"
        for span in spans
    )
    assert any(span["surface"] == "Radio London" and span["label"] == "org.ent.radiostation.bbc" for span in spans)


def test_radiostation_scoring_does_not_emit_generic_label(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(json.dumps([]), encoding="utf-8")
    write_jsonl(
        input_path,
        [
            {
                "id": "unknown-radio-1",
                "label": "org.ent.radiostation",
                "station": "unknown_radio",
                "query": "Unknown Radio",
                "language": "en",
                "snippet": "Unknown Radio is mentioned here.",
            }
        ],
    )

    result = score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    assert result["unresolved_label"] == 1
    assert scored["candidate_label"] is None
    assert scored["curation"]["label"] is None
    assert "unresolved_radiostation_label" in scored["curation"]["reasons"]
    assert scored["model"]["predicted_spans"] == []


def test_manual_span_accepts_pasted_numbered_tokens() -> None:
    row = {
        "text": "B. B. C. (1500 an 261 m).",
        "tokens": ["B", ".", "B", ".", "C", ".", "(", "1500", "an", "261", "m", ")", "."],
        "token_start_offsets": [0, 1, 3, 4, 6, 7, 9, 10, 15, 18, 22, 23, 24],
        "token_end_offsets": [1, 2, 4, 5, 7, 8, 10, 14, 17, 21, 23, 24, 25],
        "candidate_label": "org.ent.radiostation.bbc",
    }

    span = parse_manual_span("0:B 1:. 2:B 3:. 4:C 5:.", row)

    assert span["token_start"] == 0
    assert span["token_stop"] == 6
    assert span["label"] == "org.ent.radiostation.bbc"
    assert span["surface"] == "B. B. C."


def test_manual_span_accepts_canonical_id_label() -> None:
    row = {
        "text": "Londres, 15 janvier. (Radio.)",
        "tokens": ["Londres", ",", "15", "janvier", ".", "(", "Radio", ".", ")"],
        "token_start_offsets": [0, 7, 9, 12, 19, 21, 22, 27, 28],
        "token_end_offsets": [7, 8, 11, 19, 20, 22, 27, 28, 29],
        "candidate_label": None,
    }
    metadata = {
        "org.ent.pressagency.agence-radio": {
            "canonical_id": "agence-radio",
            "label": "org.ent.pressagency.agence-radio",
        }
    }

    offset_span = parse_manual_span("6:8 agence-radio", row, metadata)
    pasted_span = parse_manual_span("6:Radio 7:. agence-radio", row, metadata)

    assert offset_span["label"] == "org.ent.pressagency.agence-radio"
    assert offset_span["surface"] == "Radio."
    assert pasted_span["token_start"] == 6
    assert pasted_span["token_stop"] == 8
    assert pasted_span["label"] == "org.ent.pressagency.agence-radio"


def test_prompt_manual_spans_prints_interpretation(monkeypatch, capsys) -> None:
    row = {
        "text": "Londres, 15 janvier. (Radio.)",
        "tokens": ["Londres", ",", "15", "janvier", ".", "(", "Radio", ".", ")"],
        "token_start_offsets": [0, 7, 9, 12, 19, 21, 22, 27, 28],
        "token_end_offsets": [7, 8, 11, 19, 20, 22, 27, 28, 29],
        "candidate_label": None,
    }
    metadata = {
        "org.ent.pressagency.agence-radio": {
            "canonical_id": "agence-radio",
            "label": "org.ent.pressagency.agence-radio",
        }
    }
    answers = iter(["6:Radio 7:. agence-radio", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    spans = prompt_manual_spans(row, metadata)

    captured = capsys.readouterr()
    assert spans[0]["label"] == "org.ent.pressagency.agence-radio"
    assert 'interpreted: 6:8 "Radio." [org.ent.pressagency.agence-radio]' in captured.out


def test_prompt_manual_spans_accepts_commands_inside_span_prompt(monkeypatch, capsys) -> None:
    row = {
        "text": "A. F. P.",
        "tokens": ["A", ".", "F", ".", "P", "."],
        "token_start_offsets": [0, 1, 3, 4, 6, 7],
        "token_end_offsets": [1, 2, 4, 5, 7, 8],
        "candidate_label": "org.ent.pressagency.afp",
    }
    answers = iter(["N", "0:A 1:. 2:F 3:. 4:P 5:. afp", "y", "q"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    spans = prompt_manual_spans(row, {})

    captured = capsys.readouterr()
    assert spans is not None
    assert len(spans) == 1
    assert spans[0]["surface"] == "A. F. P."
    assert spans[0]["label"] == "org.ent.pressagency.afp"
    assert captured.out.count("numbered tokens:") == 2


def test_prompt_manual_spans_can_cancel_without_saving(monkeypatch) -> None:
    row = {
        "text": "A. F. P.",
        "tokens": ["A", ".", "F", ".", "P", "."],
        "token_start_offsets": [0, 1, 3, 4, 6, 7],
        "token_end_offsets": [1, 2, 4, 5, 7, 8],
        "candidate_label": "org.ent.pressagency.afp",
    }
    answers = iter(["q"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    assert prompt_manual_spans(row, {}) is None


def test_newsagency_manual_review_prints_numbered_tokens(tmp_path: Path, monkeypatch, capsys) -> None:
    decisions_path = tmp_path / "decisions.jsonl"
    label_metadata_path = tmp_path / "newsagency_seeds.json"
    label_metadata_path.write_text(
        json.dumps(
            [
                {
                    "label": "org.ent.pressagency.havas",
                    "display_name": "Agence Havas",
                    "description": "French news agency.",
                    "annotation_note": "Use source-formula contexts.",
                    "active_period": {"start": "1835", "end": "1940", "note": "Historical agency."},
                    "aliases_by_language": {"fr": ["Agence Havas"], "de": ["Havas"], "en": ["Havas"]},
                    "contextual_aliases": [{"alias": "H.", "note": "Only in clear Havas source formulas."}],
                    "metadata_sources": [{"type": "wikidata", "url": "https://www.wikidata.org/wiki/Q2826560"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    row = {
        "id": "snippet-1",
        "source_document_id": "JDG-1946-01-01-a-i0001",
        "source": {"source_file": "data/annotated_data/fr/newsagency-data-train-fr.tsv"},
        "query": "Havas",
        "candidate_label": "org.ent.pressagency.havas",
        "curation": {"status": "needs_review", "label": "org.ent.pressagency.havas", "reasons": ["low_confidence"]},
        "text": "Selon Havas.",
        "tokens": ["Selon", "Havas", "."],
        "token_start_offsets": [0, 6, 11],
        "token_end_offsets": [5, 11, 12],
        "model": {"predicted_spans": []},
    }
    answers = iter(["i", "", "m", "1:2 org.ent.pressagency.havas", "n", "manual boundary"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    input_path = tmp_path / "scored.jsonl"
    reviewed = review_loop([row], decisions_path, "tester", limit=0, label_metadata_path=label_metadata_path, input_path=input_path)

    captured = capsys.readouterr()
    assert reviewed == 1
    assert f"input file: {input_path}" in captured.out
    assert f"metadata file: {label_metadata_path}" in captured.out
    assert "source file: data/annotated_data/fr/newsagency-data-train-fr.tsv" in captured.out
    assert "name: Agence Havas" in captured.out
    assert "annotation note: Use source-formula contexts." in captured.out
    assert "H.: Only in clear Havas source formulas." in captured.out
    assert "impresso article: https://impresso-project.ch/app/article/JDG-1946-01-01-a-i0001" in captured.out
    assert "numbered tokens:" in captured.out
    assert "0:Selon 1:Havas 2:." in captured.out
    decision = json.loads(decisions_path.read_text(encoding="utf-8"))
    assert decision["accepted_spans"][0]["token_start"] == 1
    assert decision["accepted_spans"][0]["surface"] == "Havas"


def test_newsagency_review_accepts_multiple_prediction_spans(tmp_path: Path, monkeypatch) -> None:
    decisions_path = tmp_path / "decisions.jsonl"
    row = {
        "id": "snippet-2",
        "query": "Havas",
        "candidate_label": "org.ent.pressagency.havas",
        "curation": {"status": "needs_review", "label": "org.ent.pressagency.havas", "reasons": ["multiple_predicted_spans"]},
        "text": "Havas et Reuters confirment.",
        "tokens": ["Havas", "et", "Reuters", "confirment", "."],
        "token_start_offsets": [0, 6, 9, 17, 27],
        "token_end_offsets": [5, 8, 16, 26, 28],
        "model": {
            "predicted_spans": [
                {
                    "token_start": 0,
                    "token_stop": 1,
                    "label": "org.ent.pressagency.havas",
                    "surface": "Havas",
                    "confidence": 0.96,
                    "margin": 0.40,
                },
                {
                    "token_start": 2,
                    "token_stop": 3,
                    "label": "org.ent.pressagency.reuters",
                    "surface": "Reuters",
                    "confidence": 0.97,
                    "margin": 0.45,
                },
            ]
        },
    }
    answers = iter(["a", "a", "a", "two agencies"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    reviewed = review_loop([row], decisions_path, "tester", limit=0)

    decision = json.loads(decisions_path.read_text(encoding="utf-8"))
    assert reviewed == 1
    assert [span["label"] for span in decision["accepted_spans"]] == [
        "org.ent.pressagency.havas",
        "org.ent.pressagency.reuters",
    ]
    assert decision["notes"] == "two agencies"


def test_snippet_review_skip_is_temporary(tmp_path: Path, monkeypatch) -> None:
    decisions_path = tmp_path / "decisions.jsonl"
    row = {
        "id": "snippet-skip",
        "candidate_label": "org.ent.pressagency.havas",
        "curation": {"status": "needs_review", "label": "org.ent.pressagency.havas", "reasons": []},
        "text": "Havas.",
        "tokens": ["Havas", "."],
        "token_start_offsets": [0, 5],
        "token_end_offsets": [5, 6],
        "model": {"predicted_spans": []},
    }
    answers = iter(["s", "later", "s", "still later"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    first = review_loop([row], decisions_path, "tester", limit=1)
    second = review_loop([row], decisions_path, "tester", limit=1)

    assert first == 1
    assert second == 1
    statuses = [json.loads(line)["status"] for line in decisions_path.read_text(encoding="utf-8").splitlines()]
    assert statuses == ["skipped", "skipped"]


def test_snippet_review_remove_is_final(tmp_path: Path, monkeypatch) -> None:
    decisions_path = tmp_path / "decisions.jsonl"
    row = {
        "id": "snippet-remove",
        "candidate_label": "org.ent.pressagency.havas",
        "curation": {"status": "needs_review", "label": "org.ent.pressagency.havas", "reasons": []},
        "text": "Havas.",
        "tokens": ["Havas", "."],
        "token_start_offsets": [0, 5],
        "token_end_offsets": [5, 6],
        "model": {"predicted_spans": []},
    }
    answers = iter(["R", "bad sample"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    first = review_loop([row], decisions_path, "tester", limit=1)
    second = review_loop([row], decisions_path, "tester", limit=1)

    decision = json.loads(decisions_path.read_text(encoding="utf-8"))
    assert first == 1
    assert second == 0
    assert decision["status"] == "removed"
    assert decision["notes"] == "bad sample"


def test_radiostation_materialize_views(tmp_path: Path) -> None:
    input_rows = [
        {"id": "radio-1", "snippet": "Radio-Paris annonce le programme.", "query": "Radio-Paris"},
        {"id": "radio-2", "snippet": "Aucune station ici.", "query": "Radio-Paris"},
    ]
    decisions_path = tmp_path / "decisions.jsonl"
    output_dir = tmp_path / "views"
    write_jsonl(
        decisions_path,
        [
            {"review_id": "radiostation-snippet:radio-1", "status": "yes", "reviewer": "tester"},
            {"review_id": "radiostation-snippet:radio-2", "status": "no", "reviewer": "tester"},
        ],
    )

    counts = materialize_views(input_rows, decisions_path, output_dir)

    assert counts == {"yes": 1, "no": 1, "skip": 0}
    assert "Radio-Paris" in (output_dir / "positive_snippets.jsonl").read_text(encoding="utf-8")
    assert "Aucune station" in (output_dir / "negative_snippets.jsonl").read_text(encoding="utf-8")
