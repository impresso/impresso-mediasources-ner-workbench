from pathlib import Path

import pytest

from lib.review_curation import (
    CLEAR_SCREEN,
    clear_screen,
    format_choice_meaning,
    format_document_metadata,
    format_highlighted_context,
    format_side,
    format_token_indicator,
    latest_decisions,
    nearby_boundary_suggestions,
    parse_manual_curation_span,
    pending_items,
    prompt_manual_spans,
    prompt_notes,
    suggested_label,
)


def test_pending_items_skips_done_decisions() -> None:
    disagreements = [{"review_id": "a"}, {"review_id": "b"}]
    decisions = {"a": {"review_id": "a", "status": "done"}}

    assert pending_items(disagreements, decisions) == [{"review_id": "b"}]


def test_format_document_metadata_uses_impresso_content_item_url() -> None:
    document = {
        "id": "JDG-1970-08-24-a-i0011#match-0",
        "newspaper": "JDG",
        "date": "1970-08-24T00:00:00+00:00",
    }

    assert format_document_metadata(document) == (
        "https://impresso-project.ch/app/content-item/JDG-1970-08-24-a-i0011 JDG 1970-08-24"
    )


def test_pending_items_keeps_todo_decisions() -> None:
    disagreements = [{"review_id": "a"}]
    decisions = {"a": {"review_id": "a", "status": "todo", "choice": "skip"}}

    assert pending_items(disagreements, decisions) == [{"review_id": "a"}]


def test_pending_items_ignores_ignored_decisions() -> None:
    disagreements = [{"review_id": "a"}]
    decisions = {"a": {"review_id": "a", "status": "ignored", "choice": "skip"}}

    assert pending_items(disagreements, decisions) == []


def test_latest_decisions_uses_last_decision(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        '{"review_id": "a", "status": "done", "choice": "gold"}\n'
        '{"review_id": "a", "status": "done", "choice": "prediction"}\n',
        encoding="utf-8",
    )

    assert latest_decisions(path)["a"]["choice"] == "prediction"


def test_suggested_label_returns_selected_entity_label() -> None:
    item = {
        "gold": {"label": "org.ent.pressagency.havas"},
        "prediction": {"label": "org.ent.pressagency.afp"},
    }

    assert suggested_label(item, "gold") == "org.ent.pressagency.havas"
    assert suggested_label(item, "prediction") == "org.ent.pressagency.afp"


def test_format_token_indicator_omits_span_markers_for_copying() -> None:
    item = {
        "gold": None,
        "prediction": {"token_start": 13, "token_stop": 14},
        "context": {
            "token_start": 10,
            "token_stop": 16,
            "tokens": ["On", "télégraphie", "à", "Agence", "Wolff", "que"],
        },
    }

    assert format_token_indicator(item) == "10:On 11:télégraphie 12:à 13:Agence 14:Wolff 15:que"


def test_format_highlighted_context_marks_prediction_without_numbering() -> None:
    item = {
        "gold": None,
        "prediction": {"token_start": 13, "token_stop": 14},
        "context": {
            "token_start": 10,
            "token_stop": 16,
            "tokens": ["On", "télégraphie", "à", "Agence", "Wolff", "que"],
        },
    }

    assert format_highlighted_context(item, color=False) == "On télégraphie à **[P:Agence]** Wolff que"


def test_grouped_overlap_is_displayed_once_with_all_side_spans() -> None:
    item = {
        "gold_spans": [
            {"surface": "Agence Wolff", "label": "org.ent.pressagency.wolff", "token_start": 13, "token_stop": 15}
        ],
        "prediction_spans": [
            {"surface": "Agence", "label": "org.ent.pressagency.reuters", "token_start": 13, "token_stop": 14},
            {"surface": "Wolff", "label": "org.ent.pressagency.wolff", "token_start": 14, "token_stop": 15},
        ],
        "context": {
            "token_start": 12,
            "token_stop": 16,
            "tokens": ["'", "Agence", "Wolff", "que"],
        },
    }

    assert format_highlighted_context(item, color=False) == "' **[X:Agence]** **[X:Wolff]** que"
    assert format_side(item, "prediction") == (
        "Agence [org.ent.pressagency.reuters] tokens=13:14; "
        "Wolff [org.ent.pressagency.wolff] tokens=14:15"
    )
    lines = format_choice_meaning(item)
    assert not any("b =" in line for line in lines)
    assert any("n = keep neither side: remove all displayed" in line for line in lines)


def test_format_highlighted_context_respects_no_space_after() -> None:
    item = {
        "gold": {"token_start": 0, "token_stop": 6},
        "prediction": None,
        "context": {
            "token_start": 0,
            "token_stop": 7,
            "tokens": ["D", ".", "N", ".", "B", ".", "Ende"],
            "token_render": ["NoSpaceAfter", "NoSpaceAfter", "NoSpaceAfter", "NoSpaceAfter", "NoSpaceAfter", "_", "_"],
        },
    }

    assert format_highlighted_context(item, color=False) == "**[G:D]****[G:.]****[G:N]****[G:.]****[G:B]****[G:.]** Ende"


def test_boundary_suggestions_include_copyable_expanded_span() -> None:
    item = {
        "gold": None,
        "prediction": {"token_start": 13, "token_stop": 14, "label": "org.ent.pressagency.wolff"},
        "context": {
            "token_start": 10,
            "token_stop": 16,
            "tokens": ["On", "télégraphie", "à", "Agence", "Wolff", "que"],
        },
    }

    suggestions = nearby_boundary_suggestions(item)

    assert '13:15 "Agence Wolff" label=org.ent.pressagency.wolff' in suggestions


def test_choice_meaning_explains_none_gold_side() -> None:
    item = {
        "gold": None,
        "prediction": {"surface": "F . P", "label": "org.ent.pressagency.afp", "token_start": 768, "token_stop": 771},
    }

    lines = format_choice_meaning(item)

    assert any("g = keep the gold annotation side: <none>" in line for line in lines)
    assert any("g means keep no entity for this group" in line for line in lines)
    assert any("n = keep neither side" in line for line in lines)
    assert not any("b =" in line for line in lines)


def test_prompt_notes_skips_exact_gold_prediction_acceptance(monkeypatch: pytest.MonkeyPatch) -> None:
    item = {
        "gold": {"surface": "Havas", "label": "org.ent.pressagency.havas", "token_start": 197, "token_stop": 198},
        "prediction": None,
        "context": {"token_start": 195, "token_stop": 199, "tokens": ["presse", ",", "Havas", "."]},
    }
    monkeypatch.setattr("builtins.input", lambda _: "")

    assert prompt_notes(item, "gold") == ""


def test_prompt_notes_repeats_grouped_side_before_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    item = {
        "prediction_spans": [
            {"surface": "l'agence", "label": "org.ent.pressagency.ctk", "token_start": 67, "token_stop": 68},
            {"surface": "« Ceteka", "label": "org.ent.pressagency.ctk", "token_start": 68, "token_stop": 70},
        ]
    }
    prompts = []

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", answer)

    assert prompt_notes(item, "prediction") == ""
    assert prompts == [
        "Press Enter to keep prediction exactly: "
        "l'agence [org.ent.pressagency.ctk] tokens=67:68; "
        "« Ceteka [org.ent.pressagency.ctk] tokens=68:70; "
        "or type c to add a correction: "
    ]


def test_prompt_notes_neither_needs_no_note(monkeypatch: pytest.MonkeyPatch) -> None:
    item = {
        "gold": None,
        "prediction": {"surface": "F . P", "label": "org.ent.pressagency.afp", "token_start": 768, "token_stop": 771},
        "context": {
            "token_start": 766,
            "token_stop": 773,
            "tokens": ["A", ".", "F", ".", "P", ".", ")"],
        },
    }
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("neither must not prompt for notes"))

    assert prompt_notes(item, "neither") == ""


def test_manual_curation_span_accepts_absolute_offsets_and_canonical_id() -> None:
    item = {
        "gold": None,
        "prediction": {"surface": "HnviiH", "label": "org.ent.pressagency.ats-sda", "token_start": 1522, "token_stop": 1523},
        "context": {
            "token_start": 1520,
            "token_stop": 1525,
            "tokens": ["(", "«", "HnviiH", ".", ")"],
        },
    }
    metadata = {
        "org.ent.pressagency.ats-sda": {
            "canonical_id": "ats-sda",
            "label": "org.ent.pressagency.ats-sda",
        }
    }

    span = parse_manual_curation_span("1522:1523 ats-sda", item, metadata)

    assert span == {
        "token_start": 1522,
        "token_stop": 1523,
        "label": "org.ent.pressagency.ats-sda",
        "surface": "HnviiH",
    }


def test_manual_curation_span_accepts_pasted_numbered_token() -> None:
    item = {
        "gold": None,
        "prediction": {"surface": "HnviiH", "label": "org.ent.pressagency.ats-sda", "token_start": 1522, "token_stop": 1523},
        "context": {
            "token_start": 1520,
            "token_stop": 1525,
            "tokens": ["(", "«", "HnviiH", ".", ")"],
        },
    }

    span = parse_manual_curation_span("1522:HnviiH", item, {})

    assert span["token_start"] == 1522
    assert span["token_stop"] == 1523
    assert span["label"] == "org.ent.pressagency.ats-sda"


def test_prompt_manual_spans_prints_interpretation(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    item = {
        "gold": None,
        "prediction": {"surface": "HnviiH", "label": "org.ent.pressagency.ats-sda", "token_start": 1522, "token_stop": 1523},
        "context": {
            "token_start": 1520,
            "token_stop": 1525,
            "tokens": ["(", "«", "HnviiH", ".", ")"],
        },
    }
    answers = iter(["1522:HnviiH", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    spans = prompt_manual_spans(item)

    captured = capsys.readouterr()
    assert spans[0]["label"] == "org.ent.pressagency.ats-sda"
    assert 'interpreted: 1522:1523 "HnviiH" [org.ent.pressagency.ats-sda]' in captured.out


def test_clear_screen_writes_escape_for_interactive_terminal(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")

    clear_screen()

    assert capsys.readouterr().out == CLEAR_SCREEN
