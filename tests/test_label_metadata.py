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


def test_cip_is_a_canonical_trainable_pressagency() -> None:
    rows = load_json(ROOT / "resources" / "newsagency_seeds.json")
    cip = next(row for row in rows if row.get("canonical_id") == "cip")

    assert cip["label"] == "org.ent.pressagency.cip"
    assert cip["trainable"] is True
    assert "Agentur CIP" in cip["aliases"]
    assert cip["active_period"] == {
        "start": "1944",
        "end": "2001",
        "note": "Founded after the liberation of Belgium in 1944; the French-language Brussels agency ceased activity on 31 December 2001. French- and Dutch-language operations had become autonomous in 1991.",
    }


def test_radiostation_metadata_contract() -> None:
    rows = load_json(ROOT / "resources" / "radiostation_seeds.json")
    errors = validate_rows(
        rows,
        expected_prefix="org.ent.radiostation.",
        source=ROOT / "resources" / "radiostation_seeds.json",
    )
    assert errors == []
