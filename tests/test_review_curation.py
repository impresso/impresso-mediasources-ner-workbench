from pathlib import Path

import pytest

from lib.review_curation import (
    CLEAR_SCREEN,
    clear_screen,
    format_choice_meaning,
    format_highlighted_context,
    format_token_indicator,
    latest_decisions,
    nearby_boundary_suggestions,
    pending_items,
    prompt_notes,
    suggested_label,
)


def test_pending_items_skips_done_decisions() -> None:
    disagreements = [{"review_id": "a"}, {"review_id": "b"}]
    decisions = {"a": {"review_id": "a", "status": "done"}}

    assert pending_items(disagreements, decisions) == [{"review_id": "b"}]


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


def test_format_token_indicator_marks_prediction_span() -> None:
    item = {
        "gold": None,
        "prediction": {"token_start": 13, "token_stop": 14},
        "context": {
            "token_start": 10,
            "token_stop": 16,
            "tokens": ["On", "télégraphie", "à", "Agence", "Wolff", "que"],
        },
    }

    assert format_token_indicator(item) == "10:On 11:télégraphie 12:à [P:13:Agence] 14:Wolff 15:que"


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

    assert any("g = accept this row's gold side: <none>" in line for line in lines)
    assert any("does not select another overlapping gold span" in line for line in lines)
    assert any("partial/duplicate rows can happen" in line for line in lines)


def test_prompt_notes_skips_exact_gold_prediction_acceptance(monkeypatch: pytest.MonkeyPatch) -> None:
    item = {
        "gold": {"surface": "Havas", "label": "org.ent.pressagency.havas", "token_start": 197, "token_stop": 198},
        "prediction": None,
        "context": {"token_start": 195, "token_stop": 199, "tokens": ["presse", ",", "Havas", "."]},
    }
    monkeypatch.setattr("builtins.input", lambda _: "")

    assert prompt_notes(item, "gold") == ""


def test_prompt_notes_collects_required_neither_note(monkeypatch: pytest.MonkeyPatch) -> None:
    item = {
        "gold": None,
        "prediction": {"surface": "F . P", "label": "org.ent.pressagency.afp", "token_start": 768, "token_stop": 771},
        "context": {
            "token_start": 766,
            "token_stop": 773,
            "tokens": ["A", ".", "F", ".", "P", ".", ")"],
        },
    }
    monkeypatch.setattr("builtins.input", lambda _: 'covered by 766:772 "A . F . P ."')

    assert prompt_notes(item, "neither") == 'covered by 766:772 "A . F . P ."'


def test_clear_screen_writes_escape_for_interactive_terminal(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")

    clear_screen()

    assert capsys.readouterr().out == CLEAR_SCREEN
