import json
import random
from collections import Counter
from pathlib import Path

import lib.sample_newsagencies as sample_newsagencies
from lib.build_newsagency_snippets import build_snippets
from lib.annotation_stats import build_stats, fill_defaults, parse_args
from lib.export_snippet_training_data import apply_split_assignments, export_rows, write_split_outputs
from lib.review_newsagency_snippets import (
    confirm_annotation_finished,
    coverage_priority,
    parse_manual_span,
    prompt_manual_spans,
    prompt_prediction_spans,
    review_loop,
    row_needs_coverage,
)
from lib.sample_radiostations import load_seed_queries as load_radiostation_seed_queries, normalize_radiostation_row
from lib.sample_radiostations import parse_args as parse_radiostation_sample_args
from lib.sample_newsagencies import (
    RateLimitThrottle,
    balanced_select,
    bucket_is_undercovered,
    context_window,
    expand_candidate_with_full_content,
    extract_candidate,
    load_undercovered_bucket_missing,
    load_sample_pairs,
    load_sample_issues,
    load_seed_queries,
    load_undercovered_buckets,
    load_undercovered_labels,
    parse_args as parse_newsagency_sample_args,
    sample_pair_key,
    safe_content_text,
    safe_search,
    write_sample_registry,
)
from lib.score_radiostation_snippets import (
    find_alias_spans,
    score_rows as score_radiostation_rows,
    suppress_model_spans_covered_by_aliases,
)
from lib.score_newsagency_snippets import (
    attach_surfaces,
    curation_status,
    load_input_rows,
    normalize_dotted_acronym_spans,
    score_rows as score_newsagency_rows,
    suppress_contained_same_label_spans,
    suppress_overlapping_spans,
)
from lib.snippet_data import row_text, tokenize_with_offsets, write_jsonl


def test_tokenize_with_offsets_keeps_character_spans() -> None:
    text = "Selon l'Agence Havas."

    tokens, starts, stops = tokenize_with_offsets(text)

    assert tokens == ["Selon", "l'Agence", "Havas", "."]
    assert [text[start:stop] for start, stop in zip(starts, stops, strict=True)] == tokens


def test_candidate_text_prefers_cleaned_matches_over_generic_snippet() -> None:
    row = {
        "id": "doc-1",
        "snippet": "Generic article lead without the search term.",
        "matches": ["selon <em>Radio</em>-<em>Moscou</em> : le communiqué"],
    }

    assert row_text(row) == "selon Radio-Moscou : le communiqué"


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


def test_newsagency_curation_status_can_disable_auto_accept() -> None:
    row = {"candidate_label": "org.ent.pressagency.tanjug"}
    spans = [
        {
            "token_start": 1,
            "token_stop": 3,
            "label": "org.ent.pressagency.tanjug",
            "surface": "Tan-Jug.",
            "confidence": 1.0,
            "margin": 1.0,
        }
    ]

    assert curation_status(
        row,
        spans,
        min_confidence=0.99,
        min_margin=0.30,
        auto_accept=False,
    ) == ("needs_review", ["manual_review_required"])


def test_newsagency_scorer_missing_input_explains_next_steps(tmp_path: Path) -> None:
    candidates = tmp_path / "data" / "candidates"
    candidates.mkdir(parents=True)
    existing = candidates / "newsagency_snippets.jsonl"
    existing.write_text('{"id":"candidate-1","snippet":"Reuter meldet."}\n', encoding="utf-8")

    try:
        load_input_rows(candidates / "newsagency_search_snippets.jsonl")
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("missing input should fail")

    assert "Input JSONL does not exist" in message
    assert "make sample-media-snippets MEDIA_FAMILY=pressagency" in message
    assert f"MEDIA_SNIPPETS={existing}" in message
    assert f"- {existing}" in message


def test_newsagency_scorer_empty_input_explains_next_steps(tmp_path: Path) -> None:
    input_path = tmp_path / "data" / "candidates" / "newsagency_search_snippets.jsonl"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("", encoding="utf-8")

    try:
        load_input_rows(input_path)
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("empty input should fail")

    assert "Input JSONL is empty" in message
    assert "make sample-media-snippets MEDIA_FAMILY=pressagency" in message
    assert "make suggest-media-snippet-spans MEDIA_FAMILY=pressagency" in message


def test_newsagency_scoring_matches_radio_and_pressagency_aliases(tmp_path: Path) -> None:
    input_path = tmp_path / "newsagency_candidates.jsonl"
    scored_path = tmp_path / "newsagency_scored.jsonl"
    agency_seeds_path = tmp_path / "newsagency_seeds.json"
    radio_seeds_path = tmp_path / "radiostation_seeds.json"
    agency_seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "ata",
                    "label": "org.ent.pressagency.ata",
                    "display_name": "Albanian Telegraphic Agency",
                    "aliases": ["Albanische Nachrichtenagentur ATA", "albanische Nachrichtenagentur ATA"],
                }
            ]
        ),
        encoding="utf-8",
    )
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
    write_jsonl(
        input_path,
        [
            {
                "id": "ata-with-bbc",
                "candidate_label": "org.ent.pressagency.ata",
                "query": "Albanische Nachrichtenagentur",
                "language": "de",
                "snippet": "Wie die albanische Nachrichtenagentur ATA, die von BBC abgehört wurde, meldete.",
            }
        ],
    )

    score_newsagency_rows(
        type(
            "Args",
            (),
            {
                "input": str(input_path),
                "output": str(scored_path),
                "model": "",
                "newsagencies": str(agency_seeds_path),
                "radiostations": str(radio_seeds_path),
                "device": "cpu",
                "max_sequence_len": 512,
                "auto_accept_min_confidence": 0.99,
                "auto_accept_min_margin": 0.30,
                "auto_accept_multiple_min_confidence": 0.99,
            },
        )
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    spans = scored["model"]["predicted_spans"]
    assert any(
        span["surface"] == "albanische Nachrichtenagentur ATA"
        and span["label"] == "org.ent.pressagency.ata"
        for span in spans
    )
    assert any(span["surface"] == "BBC" and span["label"] == "org.ent.radiostation.bbc" for span in spans)
    assert "radiostation_alias_matcher" in scored["model"]["scorers"]
    assert "pressagency_alias_matcher" in scored["model"]["scorers"]


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


def test_alias_matcher_does_not_absorb_closing_parenthesis() -> None:
    tokens = ["(", "Tan-Jug", ".", ")"]

    spans = find_alias_spans(tokens, ["Tan Jug."], "org.ent.pressagency.tanjug")

    assert spans == [
        {
            "token_start": 1,
            "token_stop": 3,
            "label": "org.ent.pressagency.tanjug",
            "surface": "Tan-Jug .",
            "confidence": 1.0,
            "margin": 1.0,
            "matcher": "alias_compact",
            "alias": "Tan Jug.",
        }
    ]


def test_alias_spans_take_precedence_over_model_spans_at_same_boundary() -> None:
    model_spans = [
        {"token_start": 17, "token_stop": 18, "label": "org.ent.pressagency.ats-sda", "surface": "UTA"}
    ]
    alias_spans = [
        {
            "token_start": 17,
            "token_stop": 18,
            "label": "org.ent.pressagency.telegraphen-union",
            "surface": "UTA",
        }
    ]

    assert suppress_model_spans_covered_by_aliases(model_spans, alias_spans) == []


def test_suppress_contained_same_label_spans_keeps_full_acronym_span() -> None:
    spans = [
        {"token_start": 19, "token_stop": 25, "label": "org.ent.pressagency.afp", "surface": "A. F. P."},
        {"token_start": 19, "token_stop": 23, "label": "org.ent.pressagency.afp", "surface": "A. F."},
        {"token_start": 23, "token_stop": 24, "label": "org.ent.pressagency.afp", "surface": "P"},
    ]

    assert suppress_contained_same_label_spans(spans) == [spans[0]]


def test_suppress_overlapping_spans_keeps_longest_regardless_of_label() -> None:
    spans = [
        {
            "token_start": 25,
            "token_stop": 28,
            "label": "org.ent.pressagency.apa",
            "surface": "Austria Presse Agentur",
            "confidence": 1.0,
            "margin": 1.0,
        },
        {
            "token_start": 27,
            "token_stop": 28,
            "label": "org.ent.pressagency.tass",
            "surface": "Agentur",
            "confidence": 0.912,
            "margin": 0.837,
        },
    ]

    assert suppress_overlapping_spans(spans) == [spans[0]]


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


def test_sample_newsagencies_prefers_search_alias_queries(tmp_path: Path) -> None:
    seeds = tmp_path / "newsagency_seeds.json"
    seeds.write_text(
        json.dumps(
            [
                {
                    "label": "org.ent.pressagency.palach-press",
                    "canonical_id": "palach-press",
                    "display_name": "Palach Press",
                    "aliases": ["Palach Press", "agence de presse Palach Press"],
                    "search_aliases": ["Palach Press", "Palach"],
                    "trainable": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    queries = load_seed_queries(seeds, languages=["fr"], labels=None, max_queries_per_label=0)

    assert [query["query"] for query in queries] == ["Palach Press", "Palach"]
    assert {query["label"] for query in queries} == {"org.ent.pressagency.palach-press"}


def test_sample_newsagencies_can_shuffle_alias_choice_by_seed(tmp_path: Path) -> None:
    seeds = tmp_path / "newsagency_seeds.json"
    seeds.write_text(
        json.dumps(
            [
                {
                    "label": "org.ent.pressagency.reuters",
                    "canonical_id": "reuters",
                    "display_name": "Reuters",
                    "aliases": ["Reuters", "Reuter", "Agence Reuters", "Reuters News"],
                    "trainable": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    first = load_seed_queries(seeds, languages=["fr"], labels=None, max_queries_per_label=2, rng=random.Random(1))
    second = load_seed_queries(seeds, languages=["fr"], labels=None, max_queries_per_label=2, rng=random.Random(2))

    assert [query["query"] for query in first] != [query["query"] for query in second]
    assert len(first) == 2
    assert len(second) == 2


def test_sample_newsagencies_default_alias_shuffle_is_not_seeded() -> None:
    args = parse_newsagency_sample_args([])

    assert args.shuffle_aliases is True
    assert args.random_seed is None


def test_sample_newsagencies_loads_undercovered_labels_from_stats(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.json"
    coverage.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "label": "org.ent.pressagency.ata",
                        "family": "pressagency",
                        "missing_to_target": 20,
                        "languages": {
                            "de": {"missing_to_target": 0},
                            "fr": {"missing_to_target": 20},
                        },
                    },
                    {
                        "label": "org.ent.pressagency.havas",
                        "family": "pressagency",
                        "missing_to_target": 0,
                        "languages": {
                            "de": {"missing_to_target": 0},
                            "fr": {"missing_to_target": 0},
                        },
                    },
                    {"label": "org.ent.radiostation.bbc", "family": "radiostation", "missing_to_target": 20},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_undercovered_labels(coverage) == {"org.ent.pressagency.ata"}
    assert load_undercovered_buckets(coverage) == {("org.ent.pressagency.ata", "fr")}
    assert load_undercovered_bucket_missing(coverage) == {("org.ent.pressagency.ata", "fr"): 20}


def test_sample_newsagencies_filters_undercovered_language_buckets() -> None:
    buckets = {("org.ent.pressagency.havas", "fr"), ("org.ent.pressagency.reuters", "*")}

    assert bucket_is_undercovered("org.ent.pressagency.havas", "fr", buckets)
    assert not bucket_is_undercovered("org.ent.pressagency.havas", "de", buckets)
    assert bucket_is_undercovered("org.ent.pressagency.reuters", "de", buckets)
    assert bucket_is_undercovered("org.ent.pressagency.reuters", "en", buckets)


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
    assert row["sample_document_id"] == "DTT-1959-12-01-a-i0079"
    assert row["sample_issue_id"] == "DTT-1959-12-01-a"


def test_safe_search_rate_limit_sleeps_then_enables_request_pause() -> None:
    sleeps = []

    class RateLimitError(Exception):
        status = 429

    class Search:
        def __init__(self) -> None:
            self.calls = 0

        def find(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RateLimitError("Rate limit exceeded")
            return "ok"

    class Client:
        def __init__(self) -> None:
            self.search = Search()

    class DateRange:
        def __init__(self, *_args) -> None:
            pass

    throttle = RateLimitThrottle(cooldown_seconds=30.0, steady_pause_seconds=3.0, sleep_fn=sleeps.append)
    result, client = safe_search(
        client=Client(),
        date_range_cls=DateRange,
        term="ATA",
        language="it",
        offset=10,
        limit=10,
        year_start=1900,
        year_end=2000,
        max_retries=2,
        connect_fn=Client,
        throttle=throttle,
    )

    assert result == "ok"
    assert client.search.calls == 2
    assert sleeps == [30.0, 3.0]
    assert throttle.enabled is True


def test_safe_content_rate_limit_enables_later_request_pause() -> None:
    sleeps = []

    class RateLimitError(Exception):
        status = 429

    class ContentItems:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, _document_id):
            self.calls += 1
            if self.calls == 1:
                raise RateLimitError("Rate limit exceeded")
            return type("Result", (), {"raw": {"content": "full text"}})()

    class Client:
        def __init__(self) -> None:
            self.content_items = ContentItems()

    client = Client()
    throttle = RateLimitThrottle(cooldown_seconds=30.0, steady_pause_seconds=3.0, sleep_fn=sleeps.append)

    try:
        safe_content_text(client, "doc-1", throttle=throttle)
    except RateLimitError:
        pass
    text = safe_content_text(client, "doc-1", throttle=throttle)

    assert text == "full text"
    assert sleeps == [30.0, 3.0]
    assert throttle.enabled is True


def test_sample_main_writes_completed_pools_after_keyboard_interrupt(tmp_path: Path, monkeypatch) -> None:
    seeds = tmp_path / "seeds.json"
    out = tmp_path / "out.jsonl"
    summary = tmp_path / "summary.json"
    registry = tmp_path / "registry.jsonl"
    seeds.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "reuters",
                    "label": "org.ent.pressagency.reuters",
                    "display_name": "Reuters",
                    "aliases": ["Reuters"],
                }
            ]
        ),
        encoding="utf-8",
    )

    calls = []

    def fake_import_runtime():
        return object, lambda: object()

    def fake_collect_pool_for_bucket(**kwargs):
        calls.append(kwargs["search_language"])
        if len(calls) == 2:
            raise KeyboardInterrupt
        query = kwargs["query"]
        return [
            {
                "id": "doc-1#match-0",
                "candidate_label": query["label"],
                "query": query["query"],
                "search_language": kwargs["search_language"],
                "sample_issue_id": "doc-1",
                "source": {"document_id": "doc-1-i0001"},
            }
        ], kwargs["client"]

    monkeypatch.setattr(sample_newsagencies, "import_runtime", fake_import_runtime)
    monkeypatch.setattr(sample_newsagencies, "collect_pool_for_bucket", fake_collect_pool_for_bucket)

    exit_code = sample_newsagencies.main(
        [
            "--seeds",
            str(seeds),
            "--out",
            str(out),
            "--summary-out",
            str(summary),
            "--sample-registry",
            str(registry),
            "--languages",
            "de",
            "fr",
            "--target-per-query-lang",
            "1",
            "--pool-factor",
            "1",
        ]
    )

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert [row["id"] for row in rows] == ["doc-1#match-0"]
    assert data["interrupted"] is True
    assert data["completed_pool_buckets"] == 1
    assert data["interrupted_at"] == "org.ent.pressagency.reuters || Reuters || fr"


def test_sample_registry_and_selection_use_issue_entity_pairs(tmp_path: Path) -> None:
    registry = tmp_path / "sample_entity_pairs.jsonl"
    existing_rows = [
        {
            "id": "DTT-1959-12-01-a-i0079#match-0",
            "candidate_label": "org.ent.pressagency.reuters",
            "source": {"document_id": "DTT-1959-12-01-a-i0079"},
        }
    ]
    write_jsonl(tmp_path / "existing.jsonl", existing_rows)
    pairs = load_sample_pairs([tmp_path / "existing.jsonl"])

    assert pairs == {("DTT-1959-12-01-a", "org.ent.pressagency.reuters")}

    pools = {
        ("org.ent.pressagency.reuters", "Reuter", "de"): [
            {
                "id": "DTT-1959-12-01-a-i0080#match-0",
                "candidate_label": "org.ent.pressagency.reuters",
                "source": {"document_id": "DTT-1959-12-01-a-i0080"},
            },
            {
                "id": "DTT-1959-12-02-a-i0001#match-0",
                "candidate_label": "org.ent.pressagency.reuters",
                "source": {"document_id": "DTT-1959-12-02-a-i0001"},
            },
            {
                "id": "DTT-1959-12-03-a-i0001#match-0",
                "candidate_label": "org.ent.pressagency.reuters",
                "source": {"document_id": "DTT-1959-12-03-a-i0001"},
            },
        ]
    }
    selected, summary = balanced_select(
        pools,
        target_per_bucket=5,
        rng=random.Random(42),
        max_per_label=2,
        existing_sample_pairs=pairs,
    )
    written = write_sample_registry(registry, selected, pairs)

    assert [row["sample_issue_id"] for row in selected] == ["DTT-1959-12-02-a", "DTT-1959-12-03-a"]
    assert [sample_pair_key(row) for row in selected] == [
        ("DTT-1959-12-02-a", "org.ent.pressagency.reuters"),
        ("DTT-1959-12-03-a", "org.ent.pressagency.reuters"),
    ]
    assert summary["counts_by_label_selected"] == {"org.ent.pressagency.reuters": 2}
    assert written == 2


def test_sampling_can_exclude_existing_dataset_issues_for_any_label(tmp_path: Path) -> None:
    existing_dataset = tmp_path / "train.jsonl"
    write_jsonl(
        existing_dataset,
        [
            {
                "document_id": "DTT-1959-12-01-a-i0079#match-0",
                "label": "org.ent.pressagency.reuters",
                "legacy": {"source_document_id": "DTT-1959-12-01-a-i0079"},
            }
        ],
    )
    issues = load_sample_issues([existing_dataset])

    assert issues == {"DTT-1959-12-01-a"}

    pools = {
        ("org.ent.radiostation.radio-moscow", "Radio Moscou", "fr"): [
            {
                "id": "DTT-1959-12-01-a-i0080#match-0",
                "candidate_label": "org.ent.radiostation.radio-moscow",
                "source": {"document_id": "DTT-1959-12-01-a-i0080"},
            },
            {
                "id": "DTT-1959-12-02-a-i0001#match-0",
                "candidate_label": "org.ent.radiostation.radio-moscow",
                "source": {"document_id": "DTT-1959-12-02-a-i0001"},
            },
        ]
    }
    selected, summary = balanced_select(
        pools,
        target_per_bucket=2,
        rng=random.Random(42),
        max_per_label=2,
        existing_sample_issues=issues,
    )

    assert [row["sample_issue_id"] for row in selected] == ["DTT-1959-12-02-a"]
    assert summary["counts_by_label_selected"] == {"org.ent.radiostation.radio-moscow": 1}


def test_radiostation_sampling_can_select_full_collected_pool_for_review() -> None:
    target_pool_size = 20
    pools = {
        ("org.ent.radiostation.radio-bucharest", "Radio Bucarest", "fr"): [
            {
                "id": f"EXP-1958-03-{index:02d}-a-i0001#match-0",
                "candidate_label": "org.ent.radiostation.radio-bucharest",
                "source": {"document_id": f"EXP-1958-03-{index:02d}-a-i0001"},
            }
            for index in range(1, target_pool_size + 1)
        ]
    }

    selected, summary = balanced_select(
        pools,
        target_per_bucket=target_pool_size,
        rng=random.Random(42),
        max_per_label=target_pool_size,
    )

    assert len(selected) == target_pool_size
    assert summary["counts_by_label_selected"] == {"org.ent.radiostation.radio-bucharest": target_pool_size}


def test_sampling_uses_coverage_aware_language_bucket_targets() -> None:
    pools = {
        ("org.ent.pressagency.domei", "Domei", "lb"): [
            {
                "id": f"luxwort-1942-01-{index:02d}-a-i0001#match-0",
                "candidate_label": "org.ent.pressagency.domei",
                "source": {"document_id": f"luxwort-1942-01-{index:02d}-a-i0001"},
            }
            for index in range(1, 6)
        ]
    }

    selected, summary = balanced_select(
        pools,
        target_per_bucket=5,
        target_per_bucket_by_key={("org.ent.pressagency.domei", "Domei", "lb"): 2},
        rng=random.Random(42),
        max_per_label=20,
    )

    assert len(selected) == 2
    assert summary["target_per_label_query_language"]["org.ent.pressagency.domei || Domei || lb"] == 2
    assert summary["counts_by_label_query_language"]["org.ent.pressagency.domei || Domei || lb"] == 2


def test_sample_expands_match_to_full_content_context() -> None:
    row = {
        "id": "EXP-1953-01-08-a-i0004",
        "candidate_label": "org.ent.radiostation.radio-moscow",
        "label": "org.ent.radiostation.radio-moscow",
        "query": "Radio Moscou",
        "matches": ["tendrement à l'oreille (selon <em>Radio</em>-<em>Moscou</em>) : « Pour vous"],
        "snippet": "Déclaration d'amour La scène se passe à Moscou.",
        "source": {"type": "impresso_search_result", "document_id": "EXP-1953-01-08-a-i0004"},
    }
    content = (
        "Déclaration d'amour La scène se passe à Moscou, dans un bal costumé. "
        "Il est en Pierrot, elle en Pierrette. Et lui, tendrement à l'oreille "
        "(selon Radio-Moscou) : « Pour vous prouver mon amour, je serais capable "
        "de construire une fusée. »"
    )

    rows = expand_candidate_with_full_content(row, content, context_chars=80)

    assert rows[0]["id"] == "EXP-1953-01-08-a-i0004#match-0"
    assert rows[0]["text_source"] == "full_content_match"
    assert "selon Radio-Moscou" in rows[0]["text"]
    assert "je serais capable" in rows[0]["text"]
    assert rows[0]["match_text"] == "tendrement à l'oreille (selon Radio-Moscou) : « Pour vous"


def test_sample_full_content_context_randomizes_match_offset() -> None:
    row = {
        "id": "doc-1",
        "candidate_label": "org.ent.pressagency.tanjug",
        "label": "org.ent.pressagency.tanjug",
        "query": "Tan Jug",
        "matches": ["<em>Tan</em> <em>Jug</em>"],
        "source": {"type": "impresso_search_result", "document_id": "doc-1"},
    }
    content = (
        " ".join(f"before{i}" for i in range(40))
        + " Tan Jug "
        + " ".join(f"after{i}" for i in range(40))
    )

    first = expand_candidate_with_full_content(row, content, context_chars=80, rng=random.Random(1))[0]
    second = expand_candidate_with_full_content(row, content, context_chars=80, rng=random.Random(5))[0]

    assert "Tan Jug" in first["text"]
    assert "Tan Jug" in second["text"]
    assert first["context_start"] != second["context_start"]
    assert first["context_stop"] - first["context_start"] - (first["match_stop"] - first["match_start"]) >= 100
    assert second["context_stop"] - second["context_start"] - (second["match_stop"] - second["match_start"]) >= 100


def test_sample_random_context_keeps_following_text_when_available() -> None:
    class MaxRng:
        def randint(self, _minimum: int, maximum: int) -> int:
            return maximum

    content = (
        " ".join(f"before{i}" for i in range(60))
        + " Domei "
        + " ".join(f"after{i}" for i in range(60))
    )
    start = content.index("Domei")
    stop = start + len("Domei")

    text, _context_start, context_stop = context_window(content, start, stop, 80, rng=MaxRng())

    assert "Domei" in text
    assert "after0" in text
    assert context_stop > stop
    assert not text.rstrip().endswith("Domei")


def test_sample_radiostations_loads_specific_label_alias_queries(tmp_path: Path) -> None:
    seeds = tmp_path / "radiostation_seeds.json"
    seeds.write_text(
        json.dumps(
            [
                {
                    "label": "org.ent.radiostation.bbc",
                    "canonical_id": "bbc",
                    "display_name": "BBC",
                    "aliases": ["BBC", "Radio Londres"],
                    "aliases_by_language": {"de": ["Londoner Rundfunk"]},
                    "trainable": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    queries = load_radiostation_seed_queries(seeds, languages=["de", "fr"], labels=None, max_queries_per_label=0)
    row = normalize_radiostation_row(
        {
            "id": "doc-1",
            "label": "org.ent.radiostation.bbc",
            "candidate_label": "org.ent.radiostation.bbc",
            "agency": "bbc",
            "agency_name": "BBC",
        }
    )

    assert {query["query"] for query in queries} == {"BBC", "Radio Londres", "Londoner Rundfunk"}
    assert {query["label"] for query in queries} == {"org.ent.radiostation.bbc"}
    assert row["station"] == "bbc"
    assert row["station_name"] == "BBC"


def test_sample_radiostations_can_shuffle_alias_choice_by_seed(tmp_path: Path) -> None:
    seeds = tmp_path / "radiostation_seeds.json"
    seeds.write_text(
        json.dumps(
            [
                {
                    "label": "org.ent.radiostation.bbc",
                    "canonical_id": "bbc",
                    "display_name": "BBC",
                    "aliases": ["BBC", "Radio Londres", "Radio London", "Londoner Rundfunk"],
                    "trainable": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    first = load_radiostation_seed_queries(seeds, languages=["de", "fr"], labels=None, max_queries_per_label=2, rng=random.Random(1))
    second = load_radiostation_seed_queries(seeds, languages=["de", "fr"], labels=None, max_queries_per_label=2, rng=random.Random(2))

    assert [query["query"] for query in first] != [query["query"] for query in second]
    assert len(first) == 2
    assert len(second) == 2


def test_sample_radiostations_default_alias_shuffle_is_not_seeded() -> None:
    args = parse_radiostation_sample_args([])

    assert args.shuffle_aliases is True
    assert args.random_seed is None


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
    assert "token_label_ids" not in rows[0]
    assert "source_component" not in rows[0]
    assert "entity_id" not in rows[0]["entities"][0]
    assert "normalized_surface" not in rows[0]["entities"][0]


def test_export_snippet_training_data_extends_label_map_with_radio_metadata(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    radio_metadata_path = tmp_path / "radiostation_seeds.json"
    missing_optional_metadata = tmp_path / "newspaper_seeds.json"
    label_map_path.write_text(json.dumps({"label2id": {"O": 0}, "id2label": {"0": "O"}}), encoding="utf-8")
    radio_metadata_path.write_text(
        json.dumps([{"label": "org.ent.radiostation.bbc", "canonical_id": "bbc", "display_name": "BBC"}]),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "snippet-1",
                "snippet": "BBC annonce.",
                "language": "fr",
                "date": "1946-01-01",
                "candidate_label": "org.ent.pressagency.ata",
                "curation": {"status": "accepted", "label": "org.ent.pressagency.ata"},
                "accepted_spans": [
                    {
                        "token_start": 0,
                        "token_stop": 1,
                        "label": "org.ent.radiostation.bbc",
                    }
                ],
            }
        ],
    )

    rows = export_rows(input_path, label_map_path, extra_label_metadata=[radio_metadata_path, missing_optional_metadata])

    assert rows[0]["token_labels"] == ["B-org.ent.radiostation.bbc", "O", "O"]
    assert rows[0]["entities"][0]["label"] == "org.ent.radiostation.bbc"


def test_export_snippet_training_data_includes_rejected_snippets_as_negative_rows(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    label_map_path.write_text(json.dumps({"label2id": {"O": 0}, "id2label": {"0": "O"}}), encoding="utf-8")
    write_jsonl(
        input_path,
        [
            {
                "id": "snippet-negative",
                "text": "Radio Londres is not a source mention here.",
                "language": "en",
                "curation": {"status": "rejected", "label": "org.ent.radiostation.bbc"},
                "accepted_spans": [],
                "source": {"document_id": "snippet-negative"},
            },
            {
                "id": "snippet-removed",
                "text": "Bad OCR fragment.",
                "language": "en",
                "curation": {"status": "removed", "label": "org.ent.radiostation.bbc"},
                "accepted_spans": [],
                "source": {"document_id": "snippet-removed"},
            },
            {
                "id": "snippet-skipped",
                "text": "Unresolved example.",
                "language": "en",
                "curation": {"status": "skipped", "label": "org.ent.radiostation.bbc"},
                "accepted_spans": [],
                "source": {"document_id": "snippet-skipped"},
            },
        ],
    )

    rows = export_rows(input_path, label_map_path)

    assert [row["document_id"] for row in rows] == ["snippet-negative"]
    assert rows[0]["entities"] == []
    assert set(rows[0]["token_labels"]) == {"O"}
    assert rows[0]["quality_flags"] == ["reviewed_negative_snippet"]
    assert rows[0]["legacy"]["review_status"] == "rejected"


def test_export_snippet_training_data_splits_by_source_issue(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    train_path = tmp_path / "train.jsonl"
    test_path = tmp_path / "test.jsonl"
    label_map_path.write_text(
        json.dumps(
            {
                "label2id": {
                    "O": 0,
                    "B-org.ent.pressagency.havas": 1,
                },
                "id2label": {
                    "0": "O",
                    "1": "B-org.ent.pressagency.havas",
                },
            }
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "issue-a-i0001#match-0",
                "sample_issue_id": "issue-a",
                "text": "Havas confirme.",
                "tokens": ["Havas", "confirme", "."],
                "token_start_offsets": [0, 6, 14],
                "token_end_offsets": [5, 13, 15],
                "candidate_label": "org.ent.pressagency.havas",
                "curation": {"status": "accepted", "label": "org.ent.pressagency.havas"},
                "accepted_spans": [{"token_start": 0, "token_stop": 1, "label": "org.ent.pressagency.havas"}],
            },
            {
                "id": "issue-a-i0002#match-0",
                "sample_issue_id": "issue-a",
                "text": "Havas annonce.",
                "tokens": ["Havas", "annonce", "."],
                "token_start_offsets": [0, 6, 13],
                "token_end_offsets": [5, 12, 14],
                "candidate_label": "org.ent.pressagency.havas",
                "curation": {"status": "accepted", "label": "org.ent.pressagency.havas"},
                "accepted_spans": [{"token_start": 0, "token_stop": 1, "label": "org.ent.pressagency.havas"}],
            },
            {
                "id": "issue-b-i0001#match-0",
                "sample_issue_id": "issue-b",
                "text": "Havas publie.",
                "tokens": ["Havas", "publie", "."],
                "token_start_offsets": [0, 6, 12],
                "token_end_offsets": [5, 11, 13],
                "candidate_label": "org.ent.pressagency.havas",
                "curation": {"status": "accepted", "label": "org.ent.pressagency.havas"},
                "accepted_spans": [{"token_start": 0, "token_stop": 1, "label": "org.ent.pressagency.havas"}],
            },
        ],
    )

    rows = apply_split_assignments(export_rows(input_path, label_map_path), test_fraction=0.5, validation_fraction=0.0, seed=42)
    counts = write_split_outputs(rows, output=train_path, validation_output=None, test_output=test_path)
    train_rows = [json.loads(line) for line in train_path.read_text(encoding="utf-8").splitlines()]
    test_rows = [json.loads(line) for line in test_path.read_text(encoding="utf-8").splitlines()]

    assert counts == {"train": len(train_rows), "test": len(test_rows)}
    assert train_rows
    assert test_rows
    split_by_issue = {}
    for row in [*train_rows, *test_rows]:
        split_by_issue.setdefault(row["legacy"]["source_issue_id"], row["split"])
        assert split_by_issue[row["legacy"]["source_issue_id"]] == row["split"]
        assert "split_group" not in row


def test_export_snippets_three_way_split_keeps_one_train_group_when_possible() -> None:
    rows = [{"split_group": f"issue-{index}"} for index in range(3)]

    split_rows = apply_split_assignments(rows, test_fraction=0.1, validation_fraction=0.1, seed=42)

    assert Counter(row["split"] for row in split_rows) == {"train": 1, "validation": 1, "test": 1}


def test_annotation_stats_counts_dataset_and_snippet_coverage(tmp_path: Path) -> None:
    news_meta = tmp_path / "newsagency_seeds.json"
    radio_meta = tmp_path / "radiostation_seeds.json"
    dataset = tmp_path / "dataset.jsonl"
    news = tmp_path / "news.jsonl"
    radio = tmp_path / "radio.jsonl"
    news_reviewed = tmp_path / "news_reviewed.jsonl"
    radio_reviewed = tmp_path / "radio_reviewed.jsonl"
    news_meta.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "havas",
                    "label": "org.ent.pressagency.havas",
                    "display_name": "Havas",
                }
            ]
        ),
        encoding="utf-8",
    )
    radio_meta.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "bbc",
                    "label": "org.ent.radiostation.bbc",
                    "display_name": "BBC",
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        dataset,
        [
            {"id": "dataset-1", "language": "de", "entities": [{"label": "org.ent.pressagency.havas"}]},
            {"id": "dataset-2", "language": "fr", "entities": [{"label": "org.ent.pressagency.havas"}]},
        ],
    )
    write_jsonl(news, [{"id": "news-1", "language": "fr", "entities": [{"label": "org.ent.pressagency.havas"}]}])
    write_jsonl(radio, [{"id": "radio-1", "language": "en", "entities": [{"label": "org.ent.radiostation.bbc"}]}])
    write_jsonl(
        news_reviewed,
        [
            {
                "id": "news-pending",
                "candidate_label": "org.ent.pressagency.havas",
                "curation": {"status": "needs_review", "label": "org.ent.pressagency.havas"},
            }
        ],
    )
    write_jsonl(radio_reviewed, [])

    args = fill_defaults(
        parse_args(
            [
                "--target-per-label",
                "4",
                "--main-languages",
                "de",
                "fr",
                "en",
                "--side-languages",
                "lb",
                "it",
                "--main-target-per-label-language",
                "2",
                "--side-target-per-label-language",
                "1",
                "--label-metadata",
                str(news_meta),
                "--label-metadata",
                str(radio_meta),
                "--dataset-jsonl",
                str(dataset),
                "--newsagency-snippet-jsonl",
                str(news),
                "--radiostation-snippet-jsonl",
                str(radio),
                "--newsagency-reviewed-jsonl",
                str(news_reviewed),
                "--radiostation-reviewed-jsonl",
                str(radio_reviewed),
            ]
        )
    )

    stats = build_stats(args)
    rows = {row["label"]: row for row in stats["rows"]}

    assert rows["org.ent.pressagency.havas"]["dataset"] == 2
    assert "legacy" not in rows["org.ent.pressagency.havas"]
    assert rows["org.ent.pressagency.havas"]["newsagency_snippets"] == 1
    assert rows["org.ent.pressagency.havas"]["total"] == 3
    assert rows["org.ent.pressagency.havas"]["missing_to_target"] == 1
    assert rows["org.ent.pressagency.havas"]["languages"]["de"]["total"] == 1
    assert rows["org.ent.pressagency.havas"]["languages"]["de"]["missing_to_target"] == 1
    assert rows["org.ent.pressagency.havas"]["languages"]["fr"]["total"] == 2
    assert rows["org.ent.pressagency.havas"]["languages"]["fr"]["missing_to_target"] == 0
    assert stats["language_targets"] == {"de": 2, "en": 2, "fr": 2, "it": 1, "lb": 1}
    assert any(
        row["label"] == "org.ent.pressagency.havas" and row["language"] == "de" and row["missing_to_target"] == 1
        for row in stats["language_rows"]
    )
    assert rows["org.ent.pressagency.havas"]["pending_review"] == 1
    assert rows["org.ent.radiostation.bbc"]["radiostation_snippets"] == 1
    assert rows["org.ent.radiostation.bbc"]["missing_to_target"] == 3


def test_review_coverage_priority_prefers_undercovered_labels() -> None:
    coverage = {
        "org.ent.pressagency.ata": {
            "label": "org.ent.pressagency.ata",
            "missing_to_target": 20,
            "total": 0,
            "pending_review": 0,
        },
        "org.ent.pressagency.havas": {
            "label": "org.ent.pressagency.havas",
            "missing_to_target": 0,
            "total": 610,
            "pending_review": 134,
        },
    }
    ata_row = {"id": "ata", "candidate_label": "org.ent.pressagency.ata", "curation": {"status": "needs_review"}}
    havas_row = {"id": "havas", "candidate_label": "org.ent.pressagency.havas", "curation": {"status": "needs_review"}}

    assert row_needs_coverage(ata_row, coverage)
    assert not row_needs_coverage(havas_row, coverage)
    assert sorted([havas_row, ata_row], key=lambda row: coverage_priority(row, coverage))[0] == ata_row


def test_review_coverage_priority_uses_row_language() -> None:
    coverage = {
        "org.ent.pressagency.havas": {
            "label": "org.ent.pressagency.havas",
            "missing_to_target": 0,
            "total": 101,
            "pending_review": 0,
            "languages": {
                "de": {"missing_to_target": 0, "total": 100, "pending_review": 0},
                "fr": {"missing_to_target": 19, "total": 1, "pending_review": 2},
            },
        }
    }
    de_row = {
        "id": "havas-de",
        "language": "de",
        "candidate_label": "org.ent.pressagency.havas",
        "curation": {"status": "needs_review"},
    }
    fr_row = {
        "id": "havas-fr",
        "language": "fr",
        "candidate_label": "org.ent.pressagency.havas",
        "curation": {"status": "needs_review"},
    }

    assert not row_needs_coverage(de_row, coverage)
    assert row_needs_coverage(fr_row, coverage)
    assert sorted([de_row, fr_row], key=lambda row: coverage_priority(row, coverage))[0] == fr_row


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
    assert rows[0]["entities"][0]["status"] == "accepted"
    assert "token_label_ids" not in rows[0]
    assert "source_component" not in rows[0]
    assert "entity_id" not in rows[0]["entities"][0]


def test_export_snippet_rows_suffixes_duplicate_source_ids(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    label_map_path.write_text(
        json.dumps(
            {
                "label2id": {
                    "O": 0,
                    "B-org.ent.radiostation.bbc": 1,
                    "I-org.ent.radiostation.bbc": 2,
                },
                "id2label": {
                    "0": "O",
                    "1": "B-org.ent.radiostation.bbc",
                    "2": "I-org.ent.radiostation.bbc",
                },
            }
        ),
        encoding="utf-8",
    )
    base = {
        "id": "doc-1#match-0",
        "curation": {"status": "accepted"},
        "language": "fr",
        "date": "1950-01-01",
        "accepted_spans": [
            {
                "label": "org.ent.radiostation.bbc",
                "start": 0,
                "stop": 3,
                "surface": "BBC",
                "token_start": 0,
                "token_stop": 1,
            }
        ],
    }
    write_jsonl(
        input_path,
        [
            {**base, "snippet": "BBC annonce."},
            {**base, "snippet": "BBC confirme."},
        ],
    )

    rows = export_rows(input_path, label_map_path)

    assert len(rows) == 2
    assert rows[0]["document_id"].startswith("doc-1#match-0#snippet-")
    assert rows[1]["document_id"].startswith("doc-1#match-0#snippet-")
    assert rows[0]["document_id"] != rows[1]["document_id"]
    assert {row["legacy"]["source_id"] for row in rows} == {"doc-1#match-0"}


def test_export_snippet_rows_canonicalizes_known_label_aliases(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    label_map_path.write_text(
        json.dumps(
            {
                "label2id": {
                    "O": 0,
                    "B-org.ent.pressagency.reuters": 1,
                    "I-org.ent.pressagency.reuters": 2,
                },
                "id2label": {
                    "0": "O",
                    "1": "B-org.ent.pressagency.reuters",
                    "2": "I-org.ent.pressagency.reuters",
                },
            }
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "doc-1#match-0",
                "curation": {"status": "accepted"},
                "date": "1946-05-20",
                "language": "fr",
                "text": "Reuter annonce.",
                "tokens": ["Reuter", "annonce", "."],
                "token_start_offsets": [0, 7, 14],
                "token_end_offsets": [6, 13, 15],
                "accepted_spans": [
                    {
                        "label": "org.ent.pressagency.reuter",
                        "start": 0,
                        "stop": 6,
                        "surface": "Reuter",
                        "token_start": 0,
                        "token_stop": 1,
                    }
                ],
            }
        ],
    )

    rows = export_rows(input_path, label_map_path)

    assert rows[0]["token_labels"] == ["B-org.ent.pressagency.reuters", "O", "O"]
    assert rows[0]["entities"][0]["label"] == "org.ent.pressagency.reuters"


def test_export_snippet_rows_ignores_stale_out_of_window_accepted_spans(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    label_map_path.write_text(
        json.dumps(
            {
                "label2id": {
                    "O": 0,
                    "B-org.ent.radiostation.radio-bucharest": 1,
                    "I-org.ent.radiostation.radio-bucharest": 2,
                    "B-org.ent.pressagency.up-upi": 3,
                    "I-org.ent.pressagency.up-upi": 4,
                },
                "id2label": {
                    "0": "O",
                    "1": "B-org.ent.radiostation.radio-bucharest",
                    "2": "I-org.ent.radiostation.radio-bucharest",
                    "3": "B-org.ent.pressagency.up-upi",
                    "4": "I-org.ent.pressagency.up-upi",
                },
            }
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "doc-1#match-0",
                "curation": {"status": "accepted"},
                "date": "1959-10-26",
                "language": "fr",
                "text": "VIENNE, 26. — UPI — Radio-Bucarest annonce",
                "tokens": ["VIENNE", ",", "26", ".", "—", "UPI", "—", "Radio-Bucarest", "annonce"],
                "token_start_offsets": [0, 6, 8, 10, 12, 14, 18, 20, 36],
                "token_end_offsets": [6, 7, 10, 11, 13, 17, 19, 34, 43],
                "accepted_spans": [
                    {
                        "label": "org.ent.radiostation.radio-bucharest",
                        "start": 20,
                        "stop": 34,
                        "surface": "Radio-Bucarest",
                        "token_start": 7,
                        "token_stop": 8,
                    },
                    {
                        "label": "org.ent.radiostation.radio-bucharest",
                        "start": 217,
                        "stop": 231,
                        "surface": "Radio-Bucarest",
                        "token_start": 44,
                        "token_stop": 45,
                    },
                ],
            }
        ],
    )

    rows = export_rows(input_path, label_map_path)

    assert len(rows) == 1
    assert len(rows[0]["entities"]) == 1
    assert rows[0]["entities"][0]["surface"] == "Radio-Bucarest"
    assert rows[0]["token_labels"][7] == "B-org.ent.radiostation.radio-bucharest"


def test_export_snippet_rows_relocates_stale_span_by_unique_surface(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    label_map_path.write_text(
        json.dumps(
            {
                "label2id": {
                    "O": 0,
                    "B-org.ent.radiostation.radio-bucharest": 1,
                    "I-org.ent.radiostation.radio-bucharest": 2,
                },
                "id2label": {
                    "0": "O",
                    "1": "B-org.ent.radiostation.radio-bucharest",
                    "2": "I-org.ent.radiostation.radio-bucharest",
                },
            }
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "doc-1#match-0",
                "curation": {"status": "accepted"},
                "date": "1948-09-18",
                "language": "de",
                "text": "Rom zurückkehren. Radio Bucarest teilt mit.",
                "tokens": ["Rom", "zurückkehren", ".", "Radio", "Bucarest", "teilt", "mit", "."],
                "token_start_offsets": [0, 4, 16, 18, 24, 33, 39, 42],
                "token_end_offsets": [3, 16, 17, 23, 32, 38, 42, 43],
                "accepted_spans": [
                    {
                        "label": "org.ent.radiostation.radio-bucharest",
                        "start": 149,
                        "stop": 163,
                        "surface": "Radio Bucarest",
                        "token_start": 25,
                        "token_stop": 27,
                    }
                ],
            }
        ],
    )

    rows = export_rows(input_path, label_map_path)

    assert rows[0]["entities"][0]["start"] == 18
    assert rows[0]["entities"][0]["stop"] == 32
    assert rows[0]["entities"][0]["token_start"] == 3
    assert rows[0]["entities"][0]["token_stop"] == 5


def test_export_snippet_rows_expands_window_for_duplicate_accepted_surface(tmp_path: Path) -> None:
    input_path = tmp_path / "reviewed.jsonl"
    label_map_path = tmp_path / "label_map.json"
    label_map_path.write_text(
        json.dumps(
            {
                "label2id": {
                    "O": 0,
                    "B-org.ent.radiostation.radio-bucharest": 1,
                },
                "id2label": {
                    "0": "O",
                    "1": "B-org.ent.radiostation.radio-bucharest",
                },
            }
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "doc-1#match-0",
                "curation": {"status": "accepted"},
                "date": "1959-10-26",
                "language": "fr",
                "matches": [
                    "VIENNE — <em>Radio</em>-<em>Bucarest</em> annonce",
                    "plus tard <em>Radio</em>-<em>Bucarest</em> confirme",
                ],
                "text": "VIENNE — Radio-Bucarest annonce",
                "tokens": ["VIENNE", "—", "Radio-Bucarest", "annonce"],
                "token_start_offsets": [0, 7, 9, 25],
                    "token_end_offsets": [6, 8, 23, 31],
                "accepted_spans": [
                    {
                        "label": "org.ent.radiostation.radio-bucharest",
                        "start": 9,
                        "stop": 23,
                        "surface": "Radio-Bucarest",
                        "token_start": 2,
                        "token_stop": 3,
                    },
                    {
                        "label": "org.ent.radiostation.radio-bucharest",
                        "start": 217,
                        "stop": 232,
                        "surface": "Radio-Bucarest",
                        "token_start": 44,
                        "token_stop": 45,
                    },
                ],
            }
        ],
    )

    rows = export_rows(input_path, label_map_path)

    assert len(rows[0]["entities"]) == 2
    assert rows[0]["text"].count("Radio-Bucarest") == 2
    assert [entity["surface"] for entity in rows[0]["entities"]] == ["Radio-Bucarest", "Radio-Bucarest"]


def test_radiostation_export_extends_label_map_for_mixed_pressagency_spans(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_reviewed.jsonl"
    radio_seeds_path = tmp_path / "radiostation_seeds.json"
    agency_seeds_path = tmp_path / "newsagency_seeds.json"
    label_map_path = tmp_path / "label_map.json"
    radio_seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "bbc",
                    "label": "org.ent.radiostation.bbc",
                    "display_name": "BBC",
                    "aliases": ["BBC"],
                }
            ]
        ),
        encoding="utf-8",
    )
    agency_seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "tanjug",
                    "label": "org.ent.pressagency.tanjug",
                    "display_name": "Tanjug",
                    "aliases": ["Tan Jug"],
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
                "id": "radio-with-newsagency",
                "text": "BBC cite Tan Jug.",
                "tokens": ["BBC", "cite", "Tan", "Jug", "."],
                "token_start_offsets": [0, 4, 9, 13, 16],
                "token_end_offsets": [3, 8, 12, 16, 17],
                "language": "fr",
                "candidate_label": "org.ent.radiostation.bbc",
                "entity_family": "radiostation",
                "curation": {"status": "accepted", "label": "org.ent.radiostation.bbc"},
                "accepted_spans": [
                    {"token_start": 0, "token_stop": 1, "label": "org.ent.radiostation.bbc"},
                    {"token_start": 2, "token_stop": 4, "label": "org.ent.pressagency.tanjug"},
                ],
            }
        ],
    )

    rows = export_rows(input_path, label_map_path, extra_label_metadata=[radio_seeds_path, agency_seeds_path])

    assert rows[0]["token_labels"] == [
        "B-org.ent.radiostation.bbc",
        "O",
        "B-org.ent.pressagency.tanjug",
        "I-org.ent.pressagency.tanjug",
        "O",
    ]
    assert {entity["label"] for entity in rows[0]["entities"]} == {
        "org.ent.radiostation.bbc",
        "org.ent.pressagency.tanjug",
    }


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


def test_radiostation_scoring_finds_radio_europe_libre_as_global_alias(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "deutsche-welle",
                    "label": "org.ent.radiostation.deutsche-welle",
                    "display_name": "Deutsche Welle",
                    "aliases": ["Deutsche Welle"],
                },
                {
                    "canonical_id": "radio-free-europe",
                    "label": "org.ent.radiostation.radio-free-europe",
                    "display_name": "Radio Free Europe",
                    "aliases": ["Radio Free Europe", "Radio Europe libre"],
                    "aliases_by_language": {"fr": ["Radio Europe libre"]},
                },
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "dw-and-rfe",
                "query": "Deutsche Welle",
                "candidate_label": "org.ent.radiostation.deutsche-welle",
                "text": "avec Radio Europe libre et Deutsche Welle.",
            }
        ],
    )

    score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    labels = {span["label"] for span in scored["model"]["predicted_spans"]}
    assert "org.ent.radiostation.radio-free-europe" in labels
    assert "org.ent.radiostation.deutsche-welle" in labels


def test_radiostation_scoring_matches_voice_of_america_german_alias(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "voice-of-america",
                    "label": "org.ent.radiostation.voice-of-america",
                    "display_name": "Voice of America",
                    "aliases": ["Voice of America", "Stimme Amerikas"],
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "voice-of-america-de",
                "label": "org.ent.radiostation",
                "station": "voice_of_america",
                "query": "Voice of America",
                "language": "de",
                "snippet": "Wurde die « Stimme Amerikas » von Amerikanern sabotiert?",
            }
        ],
    )

    score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    assert scored["candidate_label"] == "org.ent.radiostation.voice-of-america"
    assert scored["curation"]["reasons"] == []
    assert scored["model"]["predicted_spans"][0]["surface"] == "Stimme Amerikas"
    assert scored["model"]["predicted_spans"][0]["label"] == "org.ent.radiostation.voice-of-america"


def test_radiostation_scoring_matches_deutsche_welle_hyphenated_station_suffix(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "deutsche-welle",
                    "label": "org.ent.radiostation.deutsche-welle",
                    "display_name": "Deutsche Welle",
                    "aliases": ["Deutsche Welle"],
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "deutsche-welle-koenigswusterhausen",
                "label": "org.ent.radiostation",
                "station": "deutsche_welle",
                "query": "Deutsche Welle",
                "language": "fr",
                "snippet": "au poste de diffusion du Deutschland Lender: Deutsche Welle-Kœnigsw",
            }
        ],
    )

    score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    assert scored["candidate_label"] == "org.ent.radiostation.deutsche-welle"
    assert scored["curation"]["reasons"] == []
    assert scored["model"]["predicted_spans"][0]["surface"] == "Deutsche Welle-Kœnigsw"
    assert scored["model"]["predicted_spans"][0]["label"] == "org.ent.radiostation.deutsche-welle"
    assert scored["model"]["predicted_spans"][0]["matcher"] == "alias_hyphenated_suffix"


def test_radiostation_scoring_matches_vatican_radio_alias(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "vatican-radio",
                    "label": "org.ent.radiostation.vatican-radio",
                    "display_name": "Vatican Radio",
                    "aliases": ["Vatican Radio", "Radio Vatican", "Radio Vatikan"],
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "radio-vatican-luxwort",
                "label": "org.ent.radiostation",
                "station": "radio_vatican",
                "query": "Radio Vatican",
                "language": "de",
                "snippet": "Nach einer Meldung von Radio Vatican bietet das Hl. Jahr 1950 den Anlass.",
            }
        ],
    )

    score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    assert scored["candidate_label"] == "org.ent.radiostation.vatican-radio"
    assert scored["curation"]["reasons"] == []
    assert scored["model"]["predicted_spans"][0]["surface"] == "Radio Vatican"
    assert scored["model"]["predicted_spans"][0]["label"] == "org.ent.radiostation.vatican-radio"


def test_radiostation_scoring_matches_vatican_radio_descriptive_alias(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "vatican-radio",
                    "label": "org.ent.radiostation.vatican-radio",
                    "display_name": "Vatican Radio",
                    "aliases": ["Radio Vatican", "radio de la Cité du Vatican"],
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "radio-vatican-city",
                "label": "org.ent.radiostation",
                "station": "radio_vatican",
                "query": "Radio Vatican",
                "language": "fr",
                "snippet": "La radio de la Cité du Vatican a diffusé une déclaration.",
            }
        ],
    )

    score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    assert scored["candidate_label"] == "org.ent.radiostation.vatican-radio"
    assert scored["curation"]["reasons"] == []
    assert scored["model"]["predicted_spans"][0]["surface"] == "radio de la Cité du Vatican"
    assert scored["model"]["predicted_spans"][0]["label"] == "org.ent.radiostation.vatican-radio"


def test_radiostation_scoring_matches_vatican_radio_french_adjectival_alias(tmp_path: Path) -> None:
    input_path = tmp_path / "radio_candidates.jsonl"
    scored_path = tmp_path / "radio_scored.jsonl"
    seeds_path = tmp_path / "radiostation_seeds.json"
    seeds_path.write_text(
        json.dumps(
            [
                {
                    "canonical_id": "vatican-radio",
                    "label": "org.ent.radiostation.vatican-radio",
                    "display_name": "Vatican Radio",
                    "aliases": ["Radio Vatican", "radio vaticane"],
                }
            ]
        ),
        encoding="utf-8",
    )
    write_jsonl(
        input_path,
        [
            {
                "id": "radio-vaticane",
                "label": "org.ent.radiostation",
                "station": "radio_vatican",
                "query": "Radio Vatican",
                "language": "fr",
                "snippet": "Les spécialistes de la radio vaticane procèdent au montage.",
            }
        ],
    )

    score_radiostation_rows(
        type("Args", (), {"input": str(input_path), "output": str(scored_path), "radiostations": str(seeds_path)})
    )

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    assert scored["candidate_label"] == "org.ent.radiostation.vatican-radio"
    assert scored["curation"]["reasons"] == []
    assert scored["model"]["predicted_spans"][0]["surface"] == "radio vaticane"
    assert scored["model"]["predicted_spans"][0]["label"] == "org.ent.radiostation.vatican-radio"


def test_radiostation_alias_matching_does_not_swallow_following_word() -> None:
    spans = find_alias_spans(
        ["Radio-Vatican", "a", "declare"],
        ["Radio Vatican", "Radio Vaticana"],
        "org.ent.radiostation.vatican-radio",
    )

    assert spans == [
        {
            "token_start": 0,
            "token_stop": 1,
            "label": "org.ent.radiostation.vatican-radio",
            "surface": "Radio-Vatican",
            "confidence": 1.0,
            "margin": 1.0,
            "matcher": "alias_compact",
            "alias": "Radio Vatican",
        }
    ]


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
                },
                {
                    "canonical_id": "radio-prague",
                    "label": "org.ent.radiostation.radio-prague",
                    "display_name": "Radio Prague",
                    "aliases": ["Radio Prague", "Radio Prag"],
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
                },
                {
                    "canonical_id": "tanjug",
                    "label": "org.ent.pressagency.tanjug",
                    "display_name": "Tanjug",
                    "aliases": ["Tanjug", "Tan Jug."],
                },
                {
                    "canonical_id": "telegraphen-union",
                    "label": "org.ent.pressagency.telegraphen-union",
                    "display_name": "Telegraphen-Union",
                    "aliases": ["Telegraphen-Union", "T.U."],
                    "contextual_aliases": [{"alias": "UTA", "use": "dispatch_source_formula"}],
                },
                {
                    "canonical_id": "wolff",
                    "label": "org.ent.pressagency.wolff",
                    "display_name": "Wolffs Telegraphisches Bureau",
                    "aliases": ["Wolff"],
                    "contextual_aliases": [{"alias": "Conti", "use": "dispatch_source_formula"}],
                },
                {
                    "canonical_id": "ctk",
                    "label": "org.ent.pressagency.ctk",
                    "display_name": "Czech News Agency",
                    "aliases": [
                        "CTK",
                        "ČTK",
                        "tschechoslowakischen Nachrichtenagentur",
                        "Tschechoslowakische Nachrichtenagentur",
                    ],
                },
                {
                    "canonical_id": "ata",
                    "label": "org.ent.pressagency.ata",
                    "display_name": "Albanian Telegraphic Agency",
                    "aliases": [
                        "ATA",
                        "albanische Nachrichtenagentur ATA",
                        "Albanische Nachrichtenagentur ATA",
                    ],
                },
                {
                    "canonical_id": "st-petersburg-telegraph-agency",
                    "label": "org.ent.pressagency.st-petersburg-telegraph-agency",
                    "display_name": "St. Petersburg Telegraph Agency",
                    "aliases": [
                        "Russische Telegraphen-Agentur",
                        "Russische Telegrafen-Agentur",
                        "Petersburger Telegraphen-Agentur",
                    ],
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
            },
            {
                "id": "radio-vatican-with-tanjug",
                "label": "org.ent.radiostation",
                "station": "radio_vatican",
                "query": "Radio Vatican",
                "language": "fr",
                "snippet": "Belgrade, 7 juillet. (Tan Jug.) — Le journal communiste publie la nouvelle.",
            },
            {
                "id": "deutsche-welle-with-uta",
                "label": "org.ent.radiostation",
                "station": "deutsche_welle",
                "query": "Deutsche Welle",
                "language": "de",
                "snippet": "Berlin, 7. Januar. (UTA) Reichspräsident v. Hindenburg sprach im Radio.",
            },
            {
                "id": "radio-context-with-conti",
                "label": "org.ent.radiostation",
                "station": "radio_prague",
                "query": "Radio Prag",
                "language": "de",
                "snippet": "Berlin, 25. Febr. (Conti.) Die Meldung wurde später im Radio verlesen; Conti blieb zu Hause.",
            },
            {
                "id": "radio-prague-with-ctk",
                "label": "org.ent.radiostation",
                "station": "radio_prague",
                "query": "Radio Prag",
                "language": "de",
                "snippet": "Nach einer von Radio Prag verbreiteten Meldung der tschechoslowakischen Nachrichtenagentur hat die Regierung berichtet.",
            },
            {
                "id": "radio-tirana-with-ata",
                "label": "org.ent.radiostation",
                "station": "radio_prague",
                "query": "Radio Prag",
                "language": "de",
                "snippet": "Die albanische Nachrichtenagentur ATA bestätigte die Meldung.",
            },
            {
                "id": "radio-context-with-russian-imperial-agency",
                "label": "org.ent.radiostation",
                "station": "radio_prague",
                "query": "Radio Prag",
                "language": "de",
                "snippet": "Die Russische Telegraphen-Agentur teilt mit, dass ein Telegramm eingetroffen ist.",
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

    scored_rows = [
        json.loads(line)
        for line in scored_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    london_scored = next(row for row in scored_rows if row["id"] == "radio-london-with-sda")
    tanjug_scored = next(row for row in scored_rows if row["id"] == "radio-vatican-with-tanjug")
    uta_scored = next(row for row in scored_rows if row["id"] == "deutsche-welle-with-uta")
    conti_scored = next(row for row in scored_rows if row["id"] == "radio-context-with-conti")
    ctk_scored = next(row for row in scored_rows if row["id"] == "radio-prague-with-ctk")
    ata_scored = next(row for row in scored_rows if row["id"] == "radio-tirana-with-ata")
    russian_imperial_scored = next(row for row in scored_rows if row["id"] == "radio-context-with-russian-imperial-agency")
    london_spans = london_scored["model"]["predicted_spans"]
    tanjug_spans = tanjug_scored["model"]["predicted_spans"]
    uta_spans = uta_scored["model"]["predicted_spans"]
    conti_spans = conti_scored["model"]["predicted_spans"]
    ctk_spans = ctk_scored["model"]["predicted_spans"]
    ata_spans = ata_scored["model"]["predicted_spans"]
    russian_imperial_spans = russian_imperial_scored["model"]["predicted_spans"]
    assert any(
        span["surface"] == "Schweizer Depeschenagentur" and span["label"] == "org.ent.pressagency.ats-sda"
        for span in london_spans
    )
    assert any(span["surface"] == "Radio London" and span["label"] == "org.ent.radiostation.bbc" for span in london_spans)
    assert any(span["surface"] == "Tan Jug." and span["label"] == "org.ent.pressagency.tanjug" for span in tanjug_spans)
    assert any(
        span["surface"] == "UTA"
        and span["label"] == "org.ent.pressagency.telegraphen-union"
        and span["matcher"] == "contextual_dispatch_source_formula"
        for span in uta_spans
    )
    conti_matches = [span for span in conti_spans if span["label"] == "org.ent.pressagency.wolff"]
    assert len(conti_matches) == 1
    assert conti_matches[0]["surface"] == "Conti"
    assert conti_matches[0]["matcher"] == "contextual_dispatch_source_formula"
    assert any(
        span["surface"] == "Radio Prag" and span["label"] == "org.ent.radiostation.radio-prague"
        for span in ctk_spans
    )
    assert any(
        span["surface"] == "tschechoslowakischen Nachrichtenagentur"
        and span["label"] == "org.ent.pressagency.ctk"
        for span in ctk_spans
    )
    assert any(
        span["surface"] == "albanische Nachrichtenagentur ATA"
        and span["label"] == "org.ent.pressagency.ata"
        for span in ata_spans
    )
    assert any(
        span["surface"] == "Russische Telegraphen-Agentur"
        and span["label"] == "org.ent.pressagency.st-petersburg-telegraph-agency"
        for span in russian_imperial_spans
    )


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


def test_manual_span_uses_candidate_label_for_pasted_numbered_token_without_label() -> None:
    row = {
        "text": "angefahren sda. Der Mann",
        "tokens": ["angefahren", "sda", ".", "Der", "Mann"],
        "token_start_offsets": [0, 11, 14, 16, 20],
        "token_end_offsets": [10, 14, 15, 19, 24],
        "candidate_label": "org.ent.pressagency.ats-sda",
    }

    span = parse_manual_span("1:sda", row)

    assert span["token_start"] == 1
    assert span["token_stop"] == 2
    assert span["label"] == "org.ent.pressagency.ats-sda"
    assert span["surface"] == "sda"


def test_manual_span_accepts_displayed_prediction_span() -> None:
    row = {
        "text": "ALBANIE LONDRES, 9 (Reuter). — L'agence albanaise de presse",
        "tokens": [
            "ALBANIE",
            "LONDRES",
            ",",
            "9",
            "(",
            "Reuter",
            ")",
            ".",
            "—",
            "L'agence",
            "albanaise",
            "de",
            "presse",
        ],
        "token_start_offsets": [0, 8, 15, 17, 19, 20, 26, 27, 29, 31, 40, 50, 53],
        "token_end_offsets": [7, 15, 16, 18, 20, 26, 27, 28, 30, 39, 49, 52, 59],
        "candidate_label": "org.ent.pressagency.ata",
    }

    span = parse_manual_span("5:6 Reuter [org.ent.pressagency.reuters]", row)

    assert span["token_start"] == 5
    assert span["token_stop"] == 6
    assert span["label"] == "org.ent.pressagency.reuters"
    assert span["surface"] == "Reuter"


def test_manual_span_accepts_full_displayed_prediction_line() -> None:
    row = {
        "text": "ALBANIE LONDRES, 9 (Reuter).",
        "tokens": ["ALBANIE", "LONDRES", ",", "9", "(", "Reuter", ")", "."],
        "token_start_offsets": [0, 8, 15, 17, 19, 20, 26, 27],
        "token_end_offsets": [7, 15, 16, 18, 20, 26, 27, 28],
        "candidate_label": "org.ent.pressagency.ata",
    }

    span = parse_manual_span("1: 5:6 Reuter [org.ent.pressagency.reuters] conf=1.000 margin=1.000", row)

    assert span["token_start"] == 5
    assert span["token_stop"] == 6
    assert span["label"] == "org.ent.pressagency.reuters"
    assert span["surface"] == "Reuter"


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
    answers = iter(["6:Radio 7:. agence-radio", "y"])
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
    answers = iter(["N", "0:A 1:. 2:F 3:. 4:P 5:. afp", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    spans = prompt_manual_spans(row, {})

    captured = capsys.readouterr()
    assert spans is not None
    assert len(spans) == 1
    assert spans[0]["surface"] == "A. F. P."
    assert spans[0]["label"] == "org.ent.pressagency.afp"
    assert captured.out.count("numbered tokens:") == 2


def test_prompt_manual_spans_can_revise_last_span(monkeypatch, capsys) -> None:
    row = {
        "text": "angefahren sda. Der Mann",
        "tokens": ["angefahren", "sda", ".", "Der", "Mann"],
        "token_start_offsets": [0, 11, 14, 16, 20],
        "token_end_offsets": [10, 14, 15, 19, 24],
        "candidate_label": "org.ent.pressagency.ats-sda",
    }
    answers = iter(["1:sda 2:.", "v", "1:sda", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    spans = prompt_manual_spans(row, {})

    captured = capsys.readouterr()
    assert spans is not None
    assert len(spans) == 1
    assert spans[0]["token_start"] == 1
    assert spans[0]["token_stop"] == 2
    assert spans[0]["label"] == "org.ent.pressagency.ats-sda"
    assert "removed last manual span; enter the revised span" in captured.out


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


def test_prediction_span_review_can_correct_to_candidate_label(monkeypatch, capsys) -> None:
    row = {
        "text": "Telegraphen-Union berichtet:",
        "tokens": ["Telegraphen-Union", "berichtet", ":"],
        "token_start_offsets": [0, 19, 28],
        "token_end_offsets": [18, 27, 29],
        "candidate_label": "org.ent.pressagency.telegraphen-union",
        "curation": {"label": "org.ent.pressagency.telegraphen-union"},
    }
    spans = [
        {
            "token_start": 0,
            "token_stop": 1,
            "label": "org.ent.pressagency.tass",
            "surface": "Telegraphen-Union",
            "confidence": 0.338,
            "margin": 0.088,
        },
        {
            "token_start": 1,
            "token_stop": 2,
            "label": "org.ent.pressagency.wolff",
            "surface": "berichtet",
            "confidence": 0.520,
            "margin": 0.256,
        },
    ]
    answers = iter(["c", "r"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    accepted = prompt_prediction_spans(row, spans, {})

    captured = capsys.readouterr()
    assert accepted == [{**spans[0], "label": "org.ent.pressagency.telegraphen-union"}]
    assert (
        "this mention differs from the sampled candidate: "
        "predicted=org.ent.pressagency.tass candidate=org.ent.pressagency.telegraphen-union"
        in captured.out
    )


def test_prediction_span_manual_correction_returns_to_next_prediction(monkeypatch) -> None:
    row = {
        "text": "ATS / AFP annonce l'agence Tanjug",
        "tokens": ["ATS", "/", "AFP", "annonce", "l'agence", "Tanjug"],
        "token_start_offsets": [0, 4, 6, 10, 18, 27],
        "token_end_offsets": [3, 5, 9, 17, 26, 33],
        "candidate_label": "org.ent.pressagency.tanjug",
        "curation": {"label": "org.ent.pressagency.tanjug"},
    }
    spans = [
        {"token_start": 5, "token_stop": 6, "label": "org.ent.pressagency.tanjug", "surface": "Tanjug"},
        {"token_start": 0, "token_stop": 1, "label": "org.ent.pressagency.ats-sda", "surface": "ATS"},
        {"token_start": 2, "token_stop": 3, "label": "org.ent.pressagency.afp", "surface": "AFP"},
    ]
    answers = iter(["m", "4:6 tanjug", "a", "a"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    accepted = prompt_prediction_spans(row, spans, {})

    assert [(span["token_start"], span["token_stop"], span["label"]) for span in accepted] == [
        (4, 6, "org.ent.pressagency.tanjug"),
        (0, 1, "org.ent.pressagency.ats-sda"),
        (2, 3, "org.ent.pressagency.afp"),
    ]


def test_accept_confirmation_can_add_missed_manual_annotation(monkeypatch) -> None:
    row = {
        "text": "APA et ADN",
        "tokens": ["APA", "et", "ADN"],
        "token_start_offsets": [0, 4, 7],
        "token_end_offsets": [3, 6, 10],
        "candidate_label": "org.ent.pressagency.apa",
    }
    accepted = [
        {
            "token_start": 0,
            "token_stop": 1,
            "label": "org.ent.pressagency.apa",
            "surface": "APA",
            "confidence": 1.0,
            "margin": 1.0,
        }
    ]
    answers = iter(["m", "2:3 org.ent.pressagency.dnb", "y", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    completed = confirm_annotation_finished(row, accepted, {})

    assert [(span["token_start"], span["token_stop"], span["label"]) for span in completed] == [
        (0, 1, "org.ent.pressagency.apa"),
        (2, 3, "org.ent.pressagency.dnb"),
    ]


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
    answers = iter(["i", "", "m", "1:2 org.ent.pressagency.havas", "y", "manual boundary"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    input_path = tmp_path / "scored.jsonl"
    reviewed = review_loop([row], decisions_path, "tester", limit=0, label_metadata_path=label_metadata_path, input_path=input_path)

    captured = capsys.readouterr()
    assert reviewed == 1
    assert (
        "newsagency-snippet:snippet-1 https://impresso-project.ch/app/content-item/JDG-1946-01-01-a-i0001"
        in captured.out
    )
    assert f"input file: {input_path}" in captured.out
    assert f"metadata file: {label_metadata_path}" in captured.out
    assert "source file: data/annotated_data/fr/newsagency-data-train-fr.tsv" in captured.out
    assert "name: Agence Havas" in captured.out
    assert "annotation note: Use source-formula contexts." in captured.out
    assert "H.: Only in clear Havas source formulas." in captured.out
    assert "impresso article: https://impresso-project.ch/app/content-item/JDG-1946-01-01-a-i0001" in captured.out
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
    answers = iter(["n", "two agencies", "a", "a", "a", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    reviewed = review_loop([row], decisions_path, "tester", limit=0)

    decision = json.loads(decisions_path.read_text(encoding="utf-8"))
    assert reviewed == 1
    assert [span["label"] for span in decision["accepted_spans"]] == [
        "org.ent.pressagency.havas",
        "org.ent.pressagency.reuters",
    ]
    assert decision["notes"] == "two agencies"


def test_newsagency_review_accepts_all_prediction_spans_with_A(tmp_path: Path, monkeypatch) -> None:
    decisions_path = tmp_path / "decisions.jsonl"
    row = {
        "id": "snippet-accept-all",
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
    answers = iter(["A"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    reviewed = review_loop([row], decisions_path, "tester", limit=0)

    decision = json.loads(decisions_path.read_text(encoding="utf-8"))
    assert reviewed == 1
    assert [span["label"] for span in decision["accepted_spans"]] == [
        "org.ent.pressagency.havas",
        "org.ent.pressagency.reuters",
    ]
    assert decision["notes"] == ""


def test_snippet_review_auto_accepted_rows_require_explicit_status(tmp_path: Path, monkeypatch) -> None:
    decisions_path = tmp_path / "decisions.jsonl"
    row = {
        "id": "snippet-auto",
        "candidate_label": "org.ent.pressagency.havas",
        "curation": {"status": "auto_accepted", "label": "org.ent.pressagency.havas", "reasons": []},
        "text": "Havas.",
        "tokens": ["Havas", "."],
        "token_start_offsets": [0, 5],
        "token_end_offsets": [5, 6],
        "model": {
            "predicted_spans": [
                {
                    "token_start": 0,
                    "token_stop": 1,
                    "label": "org.ent.pressagency.havas",
                    "surface": "Havas",
                    "confidence": 1.0,
                    "margin": 1.0,
                }
            ]
        },
    }

    assert review_loop([row], decisions_path, "tester", limit=0) == 0

    answers = iter(["a", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    reviewed = review_loop([row], decisions_path, "tester", limit=0, review_statuses={"auto_accepted"})

    decision = json.loads(decisions_path.read_text(encoding="utf-8"))
    assert reviewed == 1
    assert decision["status"] == "accepted"
    assert decision["accepted_spans"][0]["surface"] == "Havas"


def test_snippet_review_notes_are_explicit(tmp_path: Path, monkeypatch, capsys) -> None:
    decisions_path = tmp_path / "decisions.jsonl"
    row = {
        "id": "snippet-notes",
        "candidate_label": "org.ent.pressagency.havas",
        "curation": {"status": "needs_review", "label": "org.ent.pressagency.havas", "reasons": []},
        "text": "Havas.",
        "tokens": ["Havas", "."],
        "token_start_offsets": [0, 5],
        "token_end_offsets": [5, 6],
        "model": {
            "predicted_spans": [
                {
                    "token_start": 0,
                    "token_stop": 1,
                    "label": "org.ent.pressagency.havas",
                    "surface": "Havas",
                    "confidence": 0.96,
                    "margin": 0.40,
                }
            ]
        },
    }
    answers = iter(["n", "source formula", "a", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    reviewed = review_loop([row], decisions_path, "tester", limit=0)

    captured = capsys.readouterr()
    decision = json.loads(decisions_path.read_text(encoding="utf-8"))
    assert reviewed == 1
    assert "[n]otes" not in captured.out
    assert decision["notes"] == "source formula"


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
