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


def test_keystone_is_distinct_from_ats_sda_before_merger() -> None:
    rows = load_json(ROOT / "resources" / "newsagency_seeds.json")
    keystone = next(row for row in rows if row.get("canonical_id") == "keystone")
    ats_sda = next(row for row in rows if row.get("canonical_id") == "ats-sda")

    assert keystone["label"] == "org.ent.pressagency.keystone"
    assert keystone["active_period"]["start"] == "1953"
    assert keystone["active_period"]["end"] == "2017"
    assert "Keystone" in keystone["aliases"]
    assert "Keystone-SDA" in ats_sda["aliases_by_language"]["de"]


def test_radiostation_metadata_contract() -> None:
    rows = load_json(ROOT / "resources" / "radiostation_seeds.json")
    errors = validate_rows(
        rows,
        expected_prefix="org.ent.radiostation.",
        source=ROOT / "resources" / "radiostation_seeds.json",
    )
    assert errors == []


def test_rfi_is_a_multilingual_canonical_radiostation() -> None:
    rows = load_json(ROOT / "resources" / "radiostation_seeds.json")
    rfi = next(row for row in rows if row.get("canonical_id") == "rfi")

    assert rfi["label"] == "org.ent.radiostation.rfi"
    assert rfi["wikidata_url"] == "https://www.wikidata.org/wiki/Q19912"
    assert rfi["active_period"]["start"] == "1931"
    assert "Poste Colonial" in rfi["historical_station_aliases"]
    assert rfi["aliases_by_language"]["es"] == ["RFI", "Radio Francia Internacional"]
    assert rfi["aliases_by_language"]["pt"] == ["RFI", "Rádio França Internacional"]
