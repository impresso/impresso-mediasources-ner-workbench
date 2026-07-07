from __future__ import annotations

from lib.migrate_tokenization import migrate_row
from lib.tokenization import TOKENIZATION_PROFILE, tokenize_with_offsets


LABEL = "org.ent.pressagency.havas"


def row(text: str, tokens: list[str], starts: list[int], stops: list[int], labels: list[str]) -> dict:
    return {
        "id": "doc",
        "document_id": "doc",
        "schema_version": "mediaagencies-jsonl-v0.1",
        "text": text,
        "tokens": tokens,
        "token_start_offsets": starts,
        "token_end_offsets": stops,
        "token_labels": labels,
        "entities": [],
    }


def test_tokenizer_splits_ascii_and_typographic_apostrophes_identically() -> None:
    ascii_tokens, _, _ = tokenize_with_offsets("l'agence Havas")
    typographic_tokens, _, _ = tokenize_with_offsets("l’agence Havas")

    assert ascii_tokens == ["l", "'", "agence", "Havas"]
    assert typographic_tokens == ["l", "’", "agence", "Havas"]


def test_tokenizer_splits_hyphens_without_entity_knowledge() -> None:
    tokens, _, _ = tokenize_with_offsets("ATS-AFP Telegraphen–Union")

    assert tokens == ["ATS", "-", "AFP", "Telegraphen", "–", "Union"]


def test_tokenizer_splits_letter_digit_transitions() -> None:
    tokens, _, _ = tokenize_with_offsets("Havas3 C-47")

    assert tokens == ["Havas", "3", "C", "-", "47"]


def test_migration_excludes_ascii_elided_article_from_pressagency() -> None:
    migrated, changes = migrate_row(
        row(
            "l'agence Havas",
            ["l'agence", "Havas"],
            [0, 9],
            [8, 14],
            [f"B-{LABEL}", f"I-{LABEL}"],
        )
    )

    assert migrated["tokens"] == ["l", "'", "agence", "Havas"]
    assert migrated["token_labels"] == ["O", "O", f"B-{LABEL}", f"I-{LABEL}"]
    assert migrated["entities"][0]["surface"] == "agence Havas"
    assert migrated["tokenization"] == TOKENIZATION_PROFILE
    assert [change["kind"] for change in changes] == ["exclude_french_elided_article", "retokenized"]


def test_migration_excludes_typographic_elided_article_from_pressagency() -> None:
    migrated, _ = migrate_row(
        row(
            "L’agence Havas",
            ["L’agence", "Havas"],
            [0, 9],
            [8, 14],
            [f"B-{LABEL}", f"I-{LABEL}"],
        )
    )

    assert migrated["tokens"] == ["L", "’", "agence", "Havas"]
    assert migrated["token_labels"] == ["O", "O", f"B-{LABEL}", f"I-{LABEL}"]


def test_migration_preserves_entity_metadata_when_narrowing_article() -> None:
    source = row("l'agence Havas", ["l'agence", "Havas"], [0, 9], [8, 14], [f"B-{LABEL}", f"I-{LABEL}"])
    source["entities"] = [
        {
            "token_start": 0,
            "token_stop": 2,
            "start": 0,
            "stop": 14,
            "surface": "l'agence Havas",
            "label": LABEL,
            "entity_family": "pressagency",
            "status": "accepted",
            "wikidata_url": "https://www.wikidata.org/wiki/Q1",
        }
    ]

    migrated, _ = migrate_row(source)

    assert migrated["entities"][0]["wikidata_url"] == "https://www.wikidata.org/wiki/Q1"
    assert migrated["entities"][0]["surface"] == "agence Havas"


def test_migration_preserves_lexical_hyphen_inside_one_entity() -> None:
    label = "org.ent.pressagency.telegraphen-union"
    migrated, _ = migrate_row(
        row("Telegraphen-Union", ["Telegraphen-Union"], [0], [17], [f"B-{label}"])
    )

    assert migrated["tokens"] == ["Telegraphen", "-", "Union"]
    assert migrated["token_labels"] == [f"B-{label}", f"I-{label}", f"I-{label}"]


def test_migration_preserves_text_whitespace_through_offsets() -> None:
    text = "ATS  —\nAFP"
    migrated, _ = migrate_row(row(text, ["ATS", "—", "AFP"], [0, 5, 7], [3, 6, 10], ["O", "O", "O"]))

    reconstructed = []
    cursor = 0
    for token, start, stop in zip(
        migrated["tokens"], migrated["token_start_offsets"], migrated["token_end_offsets"], strict=True
    ):
        reconstructed.append(text[cursor:start])
        reconstructed.append(token)
        cursor = stop
    reconstructed.append(text[cursor:])
    assert "".join(reconstructed) == text
