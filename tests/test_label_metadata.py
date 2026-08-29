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


def test_kyodo_is_separate_from_domei() -> None:
    rows = load_json(ROOT / "resources" / "newsagency_seeds.json")
    kyodo = next(row for row in rows if row.get("canonical_id") == "kyodo")
    domei = next(row for row in rows if row.get("canonical_id") == "domei")

    assert kyodo["label"] == "org.ent.pressagency.kyodo"
    assert "Kyodo News Service" in kyodo["aliases"]
    assert kyodo["active_period"]["start"] == "1945"
    assert domei["label"] == "org.ent.pressagency.domei"


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


def test_cri_and_kol_yisrael_have_historical_boundaries() -> None:
    rows = load_json(ROOT / "resources" / "radiostation_seeds.json")
    cri = next(row for row in rows if row.get("canonical_id") == "china-radio-international")
    kol = next(row for row in rows if row.get("canonical_id") == "kol-yisrael")

    assert cri["label"] == "org.ent.radiostation.china-radio-international"
    assert "Radio-Pékin" in cri["aliases"]
    assert cri["active_period"]["start"] == "1941"
    assert kol["label"] == "org.ent.radiostation.kol-yisrael"
    assert "KOL Israël" in kol["aliases"]
    assert kol["active_period"]["end"] == "2017"


def test_deutschlandfunk_includes_1959_proposal_period() -> None:
    rows = load_json(ROOT / "resources" / "radiostation_seeds.json")
    dlf = next(row for row in rows if row.get("canonical_id") == "deutschlandfunk")

    assert dlf["label"] == "org.ent.radiostation.deutschlandfunk"
    assert dlf["wikidata_url"] == "https://www.wikidata.org/wiki/Q695328"
    assert dlf["active_period"]["start"] == "1959"
    assert "Deutschland-Funk" in dlf["aliases"]


def test_radiostation_wikidata_qids_for_sampler_seed_rows() -> None:
    rows = load_json(ROOT / "resources" / "radiostation_seeds.json")
    by_id = {row["canonical_id"]: row for row in rows}

    assert by_id["bbc"]["wikidata_url"] == "https://www.wikidata.org/wiki/Q9531"
    assert by_id["radio-paris"]["wikidata_url"] == "https://www.wikidata.org/wiki/Q1944285"
    assert by_id["radio-moscow"]["wikidata_url"] == "https://www.wikidata.org/wiki/Q18555670"
    assert by_id["radio-bucharest"]["wikidata_url"] == "https://www.wikidata.org/wiki/Q1142390"
    assert by_id["voice-of-america"]["wikidata_url"] == "https://www.wikidata.org/wiki/Q228389"
    assert by_id["radio-prague"]["wikidata_url"] == "https://www.wikidata.org/wiki/Q1939322"


def test_rfe_and_radio_liberty_have_broader_wikidata_mapping_notes() -> None:
    rows = load_json(ROOT / "resources" / "radiostation_seeds.json")
    by_id = {row["canonical_id"]: row for row in rows}

    for canonical_id in ("radio-free-europe", "radio-liberty"):
        row = by_id[canonical_id]
        assert row["wikidata_url"] == "https://www.wikidata.org/wiki/Q485500"
        assert row["wikidata_mapping"] == "broader"
        assert "combined Radio Free Europe/Radio Liberty organization" in row["wikidata_note"]
