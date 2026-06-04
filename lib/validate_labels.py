from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


FORBIDDEN_LABELS = {
    "unk",
    "org.ent.pressagency.unk",
    "pers.ind.articleauthor",
    "org.ent.pressagency.pers.ind.articleauthor",
}


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            raise ValueError(f"{path}[{idx}] must be an object")
        rows.append(row)
    return rows


def validate_rows(rows: list[dict[str, Any]], *, expected_prefix: str, source: Path) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for idx, row in enumerate(rows):
        where = f"{source}[{idx}]"
        canonical_id = row.get("canonical_id")
        label = row.get("label")
        trainable = bool(row.get("trainable", True))

        if not isinstance(canonical_id, str) or not canonical_id:
            errors.append(f"{where}: missing canonical_id")
        elif canonical_id in seen:
            errors.append(f"{where}: duplicate canonical_id {canonical_id!r}")
        else:
            seen.add(canonical_id)

        if trainable:
            if not isinstance(label, str) or not label:
                errors.append(f"{where}: trainable row must have label")
            elif not label.startswith(expected_prefix):
                errors.append(f"{where}: label {label!r} must start with {expected_prefix!r}")
            if label in FORBIDDEN_LABELS or canonical_id in {"unk", "pers.ind.articleauthor"}:
                errors.append(f"{where}: forbidden trainable label {label!r}")
            if canonical_id == "ag":
                errors.append(f"{where}: unresolved bare 'ag' cannot be trainable")

        wikipedia_url = row.get("wikipedia_url")
        if trainable and expected_prefix == "org.ent.pressagency.":
            if not (isinstance(wikipedia_url, str) and wikipedia_url.startswith("https://")):
                errors.append(f"{where}: trainable news-agency row must have wikipedia_url")
            description = row.get("description")
            if not (isinstance(description, str) and description.strip()):
                errors.append(f"{where}: trainable news-agency row must have description")
            active_period = row.get("active_period")
            if not isinstance(active_period, dict) or "start" not in active_period or "end" not in active_period:
                errors.append(f"{where}: trainable news-agency row must have active_period with start/end")
            aliases_by_language = row.get("aliases_by_language")
            if not isinstance(aliases_by_language, dict) or not any(aliases_by_language.get(lang) for lang in ("de", "fr", "en")):
                errors.append(f"{where}: trainable news-agency row must have aliases_by_language")

    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate media-source label metadata.")
    parser.add_argument("--newsagencies", type=Path, required=True)
    parser.add_argument("--radiostations", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    errors: list[str] = []
    errors.extend(
        validate_rows(
            load_json(args.newsagencies),
            expected_prefix="org.ent.pressagency.",
            source=args.newsagencies,
        )
    )
    errors.extend(
        validate_rows(
            load_json(args.radiostations),
            expected_prefix="org.ent.radiostation.",
            source=args.radiostations,
        )
    )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("label metadata ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
