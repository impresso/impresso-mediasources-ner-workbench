from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .snippet_data import load_jsonl


def path_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_load_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    return load_json(path)


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return load_jsonl(path)


def count_jsonl(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def training_counts(path: Path) -> dict[str, Any]:
    rows = jsonl_rows(path)
    labels: Counter[str] = Counter()
    entities = 0
    tokens = 0
    for row in rows:
        tokens += len(row.get("tokens") or [])
        for entity in row.get("entities") or []:
            label = str(entity.get("label") or "")
            if label:
                labels[label] += 1
                entities += 1
    return {
        **path_state(path),
        "rows": len(rows),
        "tokens": tokens,
        "entities": entities,
        "labels": dict(sorted(labels.items())),
    }


def row_document_id(row: dict[str, Any]) -> str:
    return str(row.get("document_id") or row.get("id") or "")


def document_ids(path: Path) -> set[str]:
    return {row_document_id(row) for row in jsonl_rows(path) if row_document_id(row)}


def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        status = str((row.get("curation") or {}).get("status") or "missing")
        counts[status] += 1
    return dict(sorted(counts.items()))


def span_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    predicted = 0
    accepted = 0
    rows_with_predictions = 0
    rows_with_accepted = 0
    for row in rows:
        model = row.get("model") if isinstance(row.get("model"), dict) else {}
        predicted_spans = model.get("predicted_spans") if isinstance(model, dict) else []
        accepted_spans = row.get("accepted_spans") if isinstance(row.get("accepted_spans"), list) else []
        if isinstance(predicted_spans, list):
            predicted += len(predicted_spans)
            rows_with_predictions += int(bool(predicted_spans))
        accepted += len(accepted_spans)
        rows_with_accepted += int(bool(accepted_spans))
    return {
        "predicted_spans": predicted,
        "accepted_spans": accepted,
        "rows_with_predictions": rows_with_predictions,
        "rows_with_accepted_spans": rows_with_accepted,
    }


def latest_status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return status_counts(rows)


TERMINAL_SNIPPET_STATUSES = {"accepted", "auto_accepted", "rejected", "removed"}


def snippet_workflow_state(
    *,
    candidates_rows: int,
    scored_rows: list[dict[str, Any]],
    reviewed_rows: list[dict[str, Any]],
    split_rows: int,
    split_entities: int,
    split_document_ids: set[str],
    promoted_document_ids: set[str],
) -> dict[str, Any]:
    scored_statuses = latest_status_counts(scored_rows)
    reviewed_statuses = latest_status_counts(reviewed_rows)
    terminal_reviewed_ids = {
        row_document_id(row)
        for row in reviewed_rows
        if str((row.get("curation") or {}).get("status") or "") in TERMINAL_SNIPPET_STATUSES
    }
    reviewable_scored_ids = {
        row_document_id(row)
        for row in scored_rows
        if str((row.get("curation") or {}).get("status") or "") in {"needs_review", "auto_accepted"}
    }
    pending_review = len(reviewable_scored_ids - terminal_reviewed_ids)
    positive = sum(
        1
        for row in reviewed_rows
        if str((row.get("curation") or {}).get("status") or "") in {"accepted", "auto_accepted"}
        and bool(row.get("accepted_spans"))
    )
    negative = reviewed_statuses.get("rejected", 0)
    trainable = positive + negative
    not_usable = reviewed_statuses.get("removed", 0)
    skipped = reviewed_statuses.get("skipped", 0)
    curated = positive + negative + not_usable
    promoted_rows = len(split_document_ids & promoted_document_ids)
    unpromoted_rows = max(split_rows - promoted_rows, 0)

    if candidates_rows and not scored_rows:
        next_action = "suggest spans"
    elif pending_review:
        next_action = "review snippets"
    elif trainable and split_rows < trainable:
        next_action = "split snippets"
    elif unpromoted_rows:
        next_action = "promote snippets"
    else:
        next_action = "up to date" if split_rows else "sample snippets"

    return {
        "sampled": candidates_rows,
        "suggested": len(scored_rows),
        "pending_review": pending_review,
        "curated": curated,
        "accepted_for_dataset": positive,
        "negative_for_dataset": negative,
        "trainable_for_dataset": trainable,
        "not_usable": not_usable,
        "skipped": skipped,
        "split_rows": split_rows,
        "split_entities": split_entities,
        "promoted_rows": promoted_rows,
        "unpromoted_rows": unpromoted_rows,
        "next_action": next_action,
    }


def snippet_family_state(
    *,
    family: str,
    candidates: Path,
    sample_summary: Path,
    scored: Path,
    reviewed: Path,
    decisions: Path,
    train_jsonl: Path,
    validation_jsonl: Path,
    test_jsonl: Path,
    dataset_source_dir: Path,
) -> dict[str, Any]:
    candidate_rows = count_jsonl(candidates)
    scored_rows = jsonl_rows(scored)
    reviewed_rows = jsonl_rows(reviewed)
    sample_summary_data = safe_load_json(sample_summary)
    split_train = training_counts(train_jsonl)
    split_validation = training_counts(validation_jsonl)
    split_test = training_counts(test_jsonl)
    split_rows = split_train["rows"] + split_validation["rows"] + split_test["rows"]
    split_entities = split_train["entities"] + split_validation["entities"] + split_test["entities"]
    split_document_ids = document_ids(train_jsonl) | document_ids(validation_jsonl) | document_ids(test_jsonl)
    promoted_document_ids = (
        document_ids(dataset_source_dir / "train.jsonl")
        | document_ids(dataset_source_dir / "validation.jsonl")
        | document_ids(dataset_source_dir / "test.jsonl")
    )
    workflow = snippet_workflow_state(
        candidates_rows=candidate_rows,
        scored_rows=scored_rows,
        reviewed_rows=reviewed_rows,
        split_rows=split_rows,
        split_entities=split_entities,
        split_document_ids=split_document_ids,
        promoted_document_ids=promoted_document_ids,
    )
    return {
        "family": family,
        "workflow": workflow,
        "candidates": {**path_state(candidates), "rows": candidate_rows},
        "sample_summary": {
            **path_state(sample_summary),
            "summary": sample_summary_data,
        },
        "scored": {
            **path_state(scored),
            "rows": len(scored_rows),
            "statuses": status_counts(scored_rows),
            **span_counts(scored_rows),
        },
        "reviewed": {
            **path_state(reviewed),
            "rows": len(reviewed_rows),
            "statuses": status_counts(reviewed_rows),
            **span_counts(reviewed_rows),
        },
        "decisions": {**path_state(decisions), "rows": count_jsonl(decisions)},
        "split": {
            "train": split_train,
            "validation": split_validation,
            "test": split_test,
            "total_rows": split_rows,
            "total_entities": split_entities,
        },
        "exported": {
            "train": split_train,
            "validation": split_validation,
            "test": split_test,
            "total_rows": split_rows,
            "total_entities": split_entities,
        },
    }


def legacy_curation_state(args: argparse.Namespace) -> dict[str, Any]:
    review_dir = Path(args.curation_output_dir) / "review"
    applied_dir = Path(args.curation_applied_dir)
    return {
        "input_dir": path_state(Path(args.curation_input_dir)),
        "review_dir": path_state(review_dir),
        "all_disagreements": {**path_state(review_dir / "all_disagreements.jsonl"), "rows": count_jsonl(review_dir / "all_disagreements.jsonl")},
        "todo_disagreements": {**path_state(review_dir / "todo_disagreements.jsonl"), "rows": count_jsonl(review_dir / "todo_disagreements.jsonl")},
        "decisions": {**path_state(review_dir / "decisions.jsonl"), "rows": count_jsonl(review_dir / "decisions.jsonl")},
        "applied_dir": path_state(applied_dir),
        "applied_summary": safe_load_json(applied_dir / "curation_summary.json"),
        "applied_splits": {
            split: training_counts(applied_dir / f"{split}.jsonl")
            for split in ("train", "validation", "test")
        },
    }


def dataset_state(args: argparse.Namespace) -> dict[str, Any]:
    staging_dir = Path(args.dataset_output_dir)
    staging_summary = safe_load_json(staging_dir / "dataset_summary.json")
    local_hub_dir = Path(args.hub_dataset_dir)
    local_hub_summary = safe_load_json(local_hub_dir / "dataset_summary.json")
    published = {
        "repo_id": args.dataset,
        "configured_revision": args.dataset_revision,
        "remote_checked": False,
    }
    if args.fetch_published:
        published.update(fetch_published_dataset_state(args.dataset, args.dataset_revision))
    return {
        "source_dir": path_state(Path(args.dataset_source_dir)),
        "staging_dir": path_state(staging_dir),
        "staging_summary": staging_summary,
        "local_hub_dir": path_state(local_hub_dir),
        "local_hub_summary": local_hub_summary,
        "published": published,
    }


def fetch_published_dataset_state(repo_id: str, revision: str) -> dict[str, Any]:
    try:
        from huggingface_hub import HfApi

        api = HfApi()
        info = api.dataset_info(repo_id=repo_id, revision=None if revision in {"", "TODO"} else revision)
        siblings = [sibling.rfilename for sibling in info.siblings or []]
        return {
            "remote_checked": True,
            "sha": getattr(info, "sha", None),
            "last_modified": str(getattr(info, "last_modified", "") or ""),
            "files": sorted(siblings),
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - depends on optional network/API state.
        return {"remote_checked": True, "error": str(exc)}


def build_state(args: argparse.Namespace) -> dict[str, Any]:
    snippets = {
        "newsagencies": snippet_family_state(
            family="newsagencies",
            candidates=Path(args.newsagency_snippets),
            sample_summary=Path(args.newsagency_snippet_summary),
            scored=Path(args.newsagency_scored_snippets),
            reviewed=Path(args.newsagency_reviewed_snippets),
            decisions=Path(args.newsagency_snippet_decisions),
            train_jsonl=Path(args.newsagency_snippet_train_jsonl),
            validation_jsonl=Path(args.newsagency_snippet_validation_jsonl),
            test_jsonl=Path(args.newsagency_snippet_test_jsonl),
            dataset_source_dir=Path(args.dataset_source_dir),
        ),
        "radiostations": snippet_family_state(
            family="radiostations",
            candidates=Path(args.radiostation_snippets),
            sample_summary=Path(args.radiostation_snippet_summary),
            scored=Path(args.radiostation_scored_snippets),
            reviewed=Path(args.radiostation_reviewed_snippets),
            decisions=Path(args.radiostation_snippet_decisions),
            train_jsonl=Path(args.radiostation_snippet_train_jsonl),
            validation_jsonl=Path(args.radiostation_snippet_validation_jsonl),
            test_jsonl=Path(args.radiostation_snippet_test_jsonl),
            dataset_source_dir=Path(args.dataset_source_dir),
        ),
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "snippets": snippets,
        "legacy_curation": legacy_curation_state(args),
        "dataset": dataset_state(args),
    }


def fmt_count(value: Any) -> str:
    if value is None:
        return "-"
    return str(value)


def print_snippet_state(state: dict[str, Any]) -> None:
    print("Snippet curation")
    print("family          sampled  suggested  to_review  reviewed  trainable  dataset_rows  in_dataset  entities  next")
    print("-" * 103)
    for family, item in state["snippets"].items():
        workflow = item.get("workflow") or {}
        print(
            f"{family:<14}  "
            f"{workflow.get('sampled', item['candidates']['rows']):>7}  "
            f"{workflow.get('suggested', item['scored']['rows']):>9}  "
            f"{workflow.get('pending_review', 0):>9}  "
            f"{workflow.get('curated', item['reviewed']['rows']):>8}  "
            f"{workflow.get('trainable_for_dataset', workflow.get('accepted_for_dataset', 0)):>9}  "
            f"{workflow.get('split_rows', item['split']['total_rows']):>12}  "
            f"{workflow.get('promoted_rows', 0):>10}  "
            f"{workflow.get('split_entities', item['split']['total_entities']):>8}  "
            f"{workflow.get('next_action', '-')}"
        )
    print()
    print("Meaning: to_review = suggested snippets still needing manual audit; reviewed =")
    print("snippets with a final keep/reject/remove decision; trainable = reviewed snippets")
    print("used for training, including positive rows with accepted spans and rejected rows")
    print("as confirmed negative examples; dataset_rows/entities = rows/entities produced from")
    print("trainable snippets;")
    print("in_dataset = produced snippet rows already present in the configured dataset splits.")


def print_dataset_state(state: dict[str, Any]) -> None:
    dataset = state["dataset"]
    print("Dataset state")
    print(f"source dir:  {dataset['source_dir']['path']} ({'exists' if dataset['source_dir']['exists'] else 'missing'})")
    print(f"staging dir: {dataset['staging_dir']['path']} ({'exists' if dataset['staging_dir']['exists'] else 'missing'})")
    staging_summary = dataset.get("staging_summary") or {}
    if staging_summary:
        print(f"staging splits: {staging_summary.get('splits', {})}")
        print(f"staging entities: {staging_summary.get('entities_by_split', {})}")
        print(f"staging label count: {staging_summary.get('label_count', '-')}")
    else:
        print("staging summary: missing dataset_summary.json")
    published = dataset["published"]
    print(f"published repo: {published['repo_id']}")
    print(f"configured revision: {published.get('configured_revision') or '-'}")
    if published.get("remote_checked"):
        if published.get("error"):
            print(f"remote check error: {published['error']}")
        else:
            print(f"remote sha: {published.get('sha') or '-'}")
            print(f"remote files: {len(published.get('files') or [])}")


def print_legacy_state(state: dict[str, Any]) -> None:
    legacy = state["legacy_curation"]
    print("Legacy curation")
    print(f"all disagreements:  {legacy['all_disagreements']['rows']}")
    print(f"todo disagreements: {legacy['todo_disagreements']['rows']}")
    print(f"decisions:          {legacy['decisions']['rows']}")
    summary = legacy.get("applied_summary") or {}
    if summary:
        print(f"applied decisions:  {summary.get('applied', '-')}")
        print(f"missing decisions:  {summary.get('missing', '-')}")
    else:
        print("applied summary:    missing curation_summary.json")
    for split, split_state in legacy["applied_splits"].items():
        print(f"{split:<10} rows={split_state['rows']} entities={split_state['entities']}")


def print_state(state: dict[str, Any], section: str) -> None:
    print(f"generated_at: {state['generated_at']}")
    if section in {"all", "snippets"}:
        print_snippet_state(state)
    if section == "all":
        print()
    if section in {"all", "legacy"}:
        print_legacy_state(state)
    if section == "all":
        print()
    if section in {"all", "dataset"}:
        print_dataset_state(state)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize curation and dataset pipeline state.")
    parser.add_argument("--section", choices=["all", "snippets", "legacy", "dataset"], default="all")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--fetch-published", action="store_true")
    parser.add_argument("--dataset", default="impresso-project/impresso-mediaagencies-ner-dataset")
    parser.add_argument("--dataset-revision", default="TODO")
    parser.add_argument("--dataset-source-dir", default="data/curated/legacy-import-curated")
    parser.add_argument("--dataset-output-dir", default="staging.d/datasets/impresso-mediaagencies-ner-dataset")
    parser.add_argument("--hub-dataset-dir", default="hub/impresso-mediaagencies-ner-dataset")
    parser.add_argument("--curation-output-dir", default="data/curated/legacy-eval-curation")
    parser.add_argument("--curation-input-dir", default="data/curated/legacy-import")
    parser.add_argument("--curation-applied-dir", default="data/curated/legacy-import-curated")
    parser.add_argument("--newsagency-snippets", default="data/candidates/newsagency_search_snippets.jsonl")
    parser.add_argument("--newsagency-snippet-summary", default="data/candidates/newsagency_search_snippets_summary.json")
    parser.add_argument("--newsagency-scored-snippets", default="data/curated/snippets/newsagencies/scored.jsonl")
    parser.add_argument("--newsagency-reviewed-snippets", default="data/curated/snippets/newsagencies/reviewed.jsonl")
    parser.add_argument("--newsagency-snippet-decisions", default="data/curated/snippets/newsagencies/decisions.jsonl")
    parser.add_argument("--newsagency-snippet-train-jsonl", default="data/curated/snippets/newsagencies/train.jsonl")
    parser.add_argument("--newsagency-snippet-validation-jsonl", default="data/curated/snippets/newsagencies/validation.jsonl")
    parser.add_argument("--newsagency-snippet-test-jsonl", default="data/curated/snippets/newsagencies/test.jsonl")
    parser.add_argument("--radiostation-snippets", default="data/candidates/radiostation_search_snippets.jsonl")
    parser.add_argument("--radiostation-snippet-summary", default="data/candidates/radiostation_search_snippets_summary.json")
    parser.add_argument("--radiostation-scored-snippets", default="data/curated/snippets/radiostations/scored.jsonl")
    parser.add_argument("--radiostation-reviewed-snippets", default="data/curated/snippets/radiostations/reviewed.jsonl")
    parser.add_argument("--radiostation-snippet-decisions", default="data/curated/snippets/radiostations/decisions.jsonl")
    parser.add_argument("--radiostation-snippet-train-jsonl", default="data/curated/snippets/radiostations/train.jsonl")
    parser.add_argument("--radiostation-snippet-validation-jsonl", default="data/curated/snippets/radiostations/validation.jsonl")
    parser.add_argument("--radiostation-snippet-test-jsonl", default="data/curated/snippets/radiostations/test.jsonl")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    state = build_state(args)
    print_state(state, args.section)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
