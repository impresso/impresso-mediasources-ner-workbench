from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .review_newsagency_snippets import apply_decisions
from .sample_cookbook_snippets import (
    build_candidate,
    fetch_error_reason,
    iter_predictions,
    load_content_fetcher,
    load_cookbook_jsonl,
    resolve_impresso_api_url,
)
from .snippet_data import load_jsonl, write_jsonl


def decision_candidate_id(decision: dict[str, Any]) -> str:
    return str(decision.get("candidate_id") or "").strip()


def cookbook_content_item_id(candidate_id: str) -> str:
    return candidate_id.removeprefix("cookbook-snippet:")


def recover_rows(
    *,
    predictions_path: Path,
    decisions_path: Path,
    current_rows_path: Path,
    family: str,
    review_prefix: str,
    context_chars: int,
    fetch_content,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    current_rows = load_jsonl(current_rows_path)
    current_ids = {str(row.get("id") or "") for row in current_rows}
    decisions = load_jsonl(decisions_path)
    missing_decisions = [
        decision
        for decision in decisions
        if decision_candidate_id(decision)
        and decision_candidate_id(decision).startswith("cookbook-snippet:")
        and decision_candidate_id(decision) not in current_ids
    ]
    missing_ids = {cookbook_content_item_id(decision_candidate_id(decision)) for decision in missing_decisions}
    predictions: dict[str, dict[str, Any]] = {}
    for prediction in iter_predictions(load_cookbook_jsonl(predictions_path), family):
        ci_id = str(prediction["ci_id"])
        if ci_id in missing_ids and ci_id not in predictions:
            predictions[ci_id] = prediction

    recovered_candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for ci_id in sorted(missing_ids):
        prediction = predictions.get(ci_id)
        if prediction is None:
            rejected.append({"ci_id": ci_id, "reason": "missing_cookbook_prediction"})
            continue
        try:
            content = fetch_content(ci_id)
            row, status = build_candidate(prediction, content, context_chars=context_chars)
        except Exception as exc:
            rejected.append({"ci_id": ci_id, "reason": fetch_error_reason(exc), "error": str(exc)})
            continue
        if row is None:
            rejected.append({"ci_id": ci_id, "reason": status})
            continue
        recovered_candidates.append(row)

    combined = recovered_candidates + current_rows
    reviewed = apply_decisions(combined, decisions_path, review_prefix=review_prefix)
    summary = {
        "predictions": str(predictions_path),
        "decisions": str(decisions_path),
        "current_rows": str(current_rows_path),
        "current_rows_count": len(current_rows),
        "decision_rows": len(decisions),
        "missing_decisions": len(missing_decisions),
        "missing_content_items": len(missing_ids),
        "cookbook_predictions_found": len(predictions),
        "recovered_candidates": len(recovered_candidates),
        "rejected": len(rejected),
        "output_rows": len(reviewed),
    }
    return reviewed, rejected, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover overwritten cookbook snippet review rows from append-only decisions.")
    parser.add_argument("--family", choices=["pressagency", "radiostation"], required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--current-rows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rejected-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--review-prefix", required=True)
    parser.add_argument("--context-chars", type=int, default=256)
    parser.add_argument("--impresso-api-url")
    parser.add_argument("--http-timeout", type=float, default=30.0)
    parser.add_argument("--http-retries", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    api_url = resolve_impresso_api_url(args.impresso_api_url)
    fetch_content = load_content_fetcher(api_url, timeout=max(0.1, args.http_timeout), retries=max(0, args.http_retries))
    rows, rejected, summary = recover_rows(
        predictions_path=args.predictions,
        decisions_path=args.decisions,
        current_rows_path=args.current_rows,
        family=args.family,
        review_prefix=args.review_prefix,
        context_chars=max(1, args.context_chars),
        fetch_content=fetch_content,
    )
    summary["impresso_api_url"] = api_url
    write_jsonl(args.output, rows)
    if args.rejected_output:
        write_jsonl(args.rejected_output, rejected)
        summary["rejected_output"] = str(args.rejected_output)
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
