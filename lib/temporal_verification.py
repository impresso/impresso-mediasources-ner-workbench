from __future__ import annotations

import re
from typing import Any


def document_year(row: dict[str, Any]) -> int | None:
    for value in (
        row.get("date"),
        row.get("publication_date"),
        row.get("year"),
        (row.get("source") or {}).get("date") if isinstance(row.get("source"), dict) else None,
    ):
        if value is None:
            continue
        match = re.search(r"\d{4}", str(value))
        if match:
            return int(match.group(0))
    return None


def active_start_year(metadata: dict[str, Any] | None) -> int | None:
    if not metadata:
        return None
    active_period = metadata.get("active_period")
    if not isinstance(active_period, dict):
        return None
    value = active_period.get("start")
    if value is None:
        return None
    match = re.search(r"\d{4}", str(value))
    if not match:
        return None
    return int(match.group(0))


def verify_entity_start_year(
    *,
    row: dict[str, Any],
    label: str | None,
    label_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not label:
        return {"status": "missing_label"}
    metadata = label_metadata.get(label)
    if metadata is None:
        return {"status": "missing_entity_metadata", "label": label}
    year = document_year(row)
    if year is None:
        return {"status": "unknown_document_date", "label": label}
    start_year = active_start_year(metadata)
    if start_year is None:
        return {"status": "missing_active_start", "label": label, "document_year": year}
    active_period = metadata.get("active_period") or {}
    payload: dict[str, Any] = {
        "status": "ok",
        "label": label,
        "document_year": year,
        "start_year": start_year,
    }
    if active_period.get("note"):
        payload["active_period_note"] = active_period["note"]
    if year < start_year:
        payload["status"] = "suspicious_before_start"
        payload["delta_years"] = year - start_year
    return payload
