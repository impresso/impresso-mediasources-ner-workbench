from lib.temporal_verification import verify_entity_start_year


def test_temporal_verification_warns_before_active_start() -> None:
    result = verify_entity_start_year(
        row={"date": "1975-04-21T00:00:00+00:00"},
        label="org.ent.pressagency.akp",
        label_metadata={
            "org.ent.pressagency.akp": {
                "active_period": {"start": "1978", "end": "present", "note": "Founded as SPK."}
            }
        },
    )

    assert result == {
        "status": "suspicious_before_start",
        "label": "org.ent.pressagency.akp",
        "document_year": 1975,
        "start_year": 1978,
        "active_period_note": "Founded as SPK.",
        "delta_years": -3,
    }


def test_temporal_verification_accepts_start_year_or_later() -> None:
    result = verify_entity_start_year(
        row={"date": "1978-01-01"},
        label="org.ent.pressagency.akp",
        label_metadata={"org.ent.pressagency.akp": {"active_period": {"start": "1978", "end": "present"}}},
    )

    assert result["status"] == "ok"


def test_temporal_verification_does_not_check_after_end() -> None:
    result = verify_entity_start_year(
        row={"date": "1999-01-01"},
        label="org.ent.pressagency.domei",
        label_metadata={"org.ent.pressagency.domei": {"active_period": {"start": "1936", "end": "1945"}}},
    )

    assert result["status"] == "ok"


def test_temporal_verification_handles_missing_date() -> None:
    result = verify_entity_start_year(
        row={},
        label="org.ent.pressagency.akp",
        label_metadata={"org.ent.pressagency.akp": {"active_period": {"start": "1978"}}},
    )

    assert result["status"] == "unknown_document_date"
