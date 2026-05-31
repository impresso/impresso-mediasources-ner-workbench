from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_CHOICES = {"gold", "prediction", "both", "neither", "skip"}
ALLOWED_STATUSES = {"done"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            row["_line_number"] = line_number
            rows.append(row)
    return rows


def validate_decisions(
    disagreements: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    require_complete: bool,
) -> list[str]:
    errors: list[str] = []
    disagreement_ids = {row["review_id"] for row in disagreements}
    seen: set[str] = set()
    done_ids: set[str] = set()

    for row in decisions:
        prefix = f"decisions.jsonl:{row['_line_number']}"
        review_id = row.get("review_id")
        if not review_id:
            errors.append(f"{prefix}: missing review_id")
            continue
        if review_id in seen:
            errors.append(f"{prefix}: duplicate review_id {review_id}")
        seen.add(review_id)
        if review_id not in disagreement_ids:
            errors.append(f"{prefix}: review_id does not exist in current disagreements: {review_id}")

        status = row.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}: invalid status {status!r}; expected one of {sorted(ALLOWED_STATUSES)}")
        if status == "done":
            done_ids.add(review_id)

        choice = row.get("choice")
        if choice not in ALLOWED_CHOICES:
            errors.append(f"{prefix}: invalid choice {choice!r}; expected one of {sorted(ALLOWED_CHOICES)}")
        if choice in {"gold", "prediction"} and not row.get("correct_label"):
            errors.append(f"{prefix}: correct_label is required for choice={choice}")
        if choice in {"both", "neither"} and not row.get("notes"):
            errors.append(f"{prefix}: notes are required for choice={choice}")
        if not row.get("reviewer"):
            errors.append(f"{prefix}: missing reviewer")
        if not row.get("reviewed_at"):
            errors.append(f"{prefix}: missing reviewed_at")

    if require_complete:
        missing = sorted(disagreement_ids - done_ids)
        if missing:
            preview = ", ".join(missing[:10])
            suffix = " ..." if len(missing) > 10 else ""
            errors.append(f"curation incomplete: {len(missing)} review_ids are not done: {preview}{suffix}")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate curation decisions against generated disagreement IDs.")
    parser.add_argument("--disagreements", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--require-complete", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    disagreements = load_jsonl(Path(args.disagreements))
    decisions_path = Path(args.decisions)
    if decisions_path.is_file():
        decisions = load_jsonl(decisions_path)
    elif args.require_complete:
        print(f"decisions file does not exist: {decisions_path}")
        return 1
    else:
        decisions = []
    errors = validate_decisions(disagreements, decisions, require_complete=args.require_complete)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(json.dumps({"decisions": len(decisions), "disagreements": len(disagreements), "complete": args.require_complete}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
