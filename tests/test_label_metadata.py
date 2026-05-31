from __future__ import annotations

from pathlib import Path

from lib.validate_labels import load_json, validate_rows


ROOT = Path(__file__).resolve().parents[1]


def test_newsagency_metadata_contract() -> None:
    rows = load_json(ROOT / "resources" / "newsagency_seeds.json")
    errors = validate_rows(
        rows,
        expected_prefix="org.ent.pressagency.",
        source=ROOT / "resources" / "newsagency_seeds.json",
    )
    assert errors == []


def test_radiostation_metadata_contract() -> None:
    rows = load_json(ROOT / "resources" / "radiostation_seeds.json")
    errors = validate_rows(
        rows,
        expected_prefix="org.ent.radiostation.",
        source=ROOT / "resources" / "radiostation_seeds.json",
    )
    assert errors == []
