from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .sample_newsagencies import (
    DEFAULT_CONTEXT_CHARS,
    DEFAULT_CONTEXT_SOURCE,
    DEFAULT_MAX_EMPTY_PAGES,
    DEFAULT_MAX_PER_LABEL,
    DEFAULT_MAX_PAGES,
    DEFAULT_MAX_RETRIES,
    DEFAULT_PAGE_SIZE,
    DEFAULT_PAUSE,
    DEFAULT_POOL_FACTOR,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SAMPLE_REGISTRY,
    balanced_select,
    bucket_is_undercovered,
    clean_aliases,
    collect_pool_for_bucket,
    import_runtime,
    load_sample_pairs,
    load_sample_issues,
    load_undercovered_buckets,
    load_undercovered_labels,
    parse_labels,
    write_sample_registry,
    write_jsonl,
)


DEFAULT_SEEDS = Path("resources/radiostation_seeds.json")
DEFAULT_OUT = Path("data/candidates/radiostation_search_snippets.jsonl")
DEFAULT_SUMMARY_OUT = Path("data/candidates/radiostation_search_snippets_summary.json")
DEFAULT_LANGUAGES = ["fr", "de", "en"]
DEFAULT_YEAR_START = 1920
DEFAULT_YEAR_END = 2000
DEFAULT_TARGET_PER_QUERY_LANG = 5


def load_seed_queries(
    path: Path,
    *,
    languages: list[str],
    labels: set[str] | None,
    max_queries_per_label: int,
    rng: random.Random | None = None,
) -> list[dict[str, str]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    queries: list[dict[str, str]] = []
    for row in rows:
        label = str(row.get("label", ""))
        if not label.startswith("org.ent.radiostation."):
            continue
        if labels is not None and label not in labels:
            continue
        if row.get("trainable") is False:
            continue
        aliases = clean_aliases(row, languages)
        if rng is not None:
            aliases = list(aliases)
            rng.shuffle(aliases)
        if max_queries_per_label > 0:
            aliases = aliases[:max_queries_per_label]
        canonical_id = str(row.get("canonical_id") or label.rsplit(".", 1)[-1])
        for alias in aliases:
            queries.append(
                {
                    "query": alias,
                    "label": label,
                    "canonical_id": canonical_id,
                    "display_name": str(row.get("display_name") or alias),
                }
            )
    return queries


def normalize_radiostation_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    label = str(out.get("candidate_label") or out.get("label") or "")
    canonical_id = str(out.get("agency") or "")
    if label.startswith("org.ent.radiostation."):
        out["candidate_label"] = label
        out["label"] = label
        out["station"] = canonical_id or label.rsplit(".", 1)[-1]
    if out.get("agency"):
        out.pop("agency", None)
    if out.get("agency_name"):
        out["station_name"] = out.pop("agency_name")
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Balanced Impresso sampler for radio-station search-result snippets.")
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    parser.add_argument("--languages", nargs="+", default=DEFAULT_LANGUAGES)
    parser.add_argument("--labels", default="", help="Optional whitespace-separated canonical labels to sample.")
    parser.add_argument("--coverage-json", type=Path, help="Annotation coverage JSON from make annotation-stats.")
    parser.add_argument("--only-under-target", action="store_true", help="Only sample labels still below the target in --coverage-json.")
    parser.add_argument("--min-missing", type=int, default=1, help="Minimum missing_to_target needed when --only-under-target is set.")
    parser.add_argument("--max-queries-per-label", type=int, default=3)
    parser.add_argument("--year-start", type=int, default=DEFAULT_YEAR_START)
    parser.add_argument("--year-end", type=int, default=DEFAULT_YEAR_END)
    parser.add_argument("--target-per-query-lang", type=int, default=DEFAULT_TARGET_PER_QUERY_LANG)
    parser.add_argument("--pool-factor", type=int, default=DEFAULT_POOL_FACTOR)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--max-empty-pages", type=int, default=DEFAULT_MAX_EMPTY_PAGES)
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--random-seed", type=int, default=None, help="Optional seed for reproducible alias shuffling and context windows.")
    parser.add_argument("--shuffle-aliases", action=argparse.BooleanOptionalAction, default=True, help="Shuffle aliases before applying --max-queries-per-label; enabled by default.")
    parser.add_argument("--context-source", choices=["match", "snippet", "full-content"], default=DEFAULT_CONTEXT_SOURCE)
    parser.add_argument(
        "--context-chars",
        type=int,
        default=DEFAULT_CONTEXT_CHARS,
        help=(
            "Characters to keep on each side of a full-content match. "
            "Default 256 is intended to yield roughly <=128 subtokens for typical snippets."
        ),
    )
    parser.add_argument("--max-per-label", type=int, default=DEFAULT_MAX_PER_LABEL, help="Maximum selected samples per canonical label in this sampling round.")
    parser.add_argument("--sample-registry", type=Path, default=DEFAULT_SAMPLE_REGISTRY, help="Append-only JSONL of sampled issue/entity pairs to avoid repeated sampling.")
    parser.add_argument(
        "--existing-sample-jsonl",
        type=Path,
        action="append",
        default=[],
        help="Additional existing candidate JSONL to read as already-sampled issue/entity pairs. Can be repeated.",
    )
    parser.add_argument(
        "--existing-issue-jsonl",
        type=Path,
        action="append",
        default=[],
        help="Existing dataset JSONL to read as already-sampled newspaper-date issues. Can be repeated.",
    )
    parser.add_argument("--allow-snippet-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    languages = [language.strip() for language in args.languages if language.strip()]
    labels = parse_labels(args.labels)
    undercovered_buckets: set[tuple[str, str]] = set()
    if args.only_under_target:
        if not args.coverage_json:
            raise SystemExit("--only-under-target requires --coverage-json")
        undercovered_buckets = load_undercovered_buckets(args.coverage_json, family="radiostation", min_missing=args.min_missing)
        undercovered = {label for label, _language in undercovered_buckets}
        labels = undercovered if labels is None else labels & undercovered
    rng = random.Random(args.random_seed) if args.random_seed is not None else random.Random()
    alias_rng = (random.Random(args.random_seed) if args.random_seed is not None else random.Random()) if args.shuffle_aliases else None
    queries = load_seed_queries(
        args.seeds,
        languages=languages,
        labels=labels,
        max_queries_per_label=args.max_queries_per_label,
        rng=alias_rng,
    )
    print("Seed file:", args.seeds)
    print("Queries:", len(queries))
    print("Languages:", languages)
    if args.only_under_target:
        print("Under-target labels:", len(labels or []))
        print("Under-target label-language buckets:", len(undercovered_buckets))
    print("Output:", args.out)
    print(f"Context source: {args.context_source} (context chars: {args.context_chars})")
    existing_sample_paths = [args.sample_registry, args.out, *args.existing_sample_jsonl]
    existing_sample_pairs = load_sample_pairs(existing_sample_paths)
    existing_sample_issues = load_sample_issues(args.existing_issue_jsonl)
    print("Existing issue/entity pairs:", len(existing_sample_pairs))
    print("Existing newspaper-date issues:", len(existing_sample_issues))
    if args.dry_run:
        for query in queries[:50]:
            print(f"  {query['label']} || {query['query']}")
        if len(queries) > 50:
            print(f"  ... {len(queries) - 50} more")
        return 0

    date_range_cls, connect_fn = import_runtime()
    client = connect_fn()
    require_matches = not args.allow_snippet_only
    target_pool_size = args.target_per_query_lang * args.pool_factor
    pools: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for query in queries:
        print(
            f"\n=== ALIAS SEARCH: {query['query']!r} ===\n"
            f"  canonical label: {query['label']}\n"
            f"  canonical id: {query['canonical_id']}\n"
            f"  display name: {query['display_name']}\n"
            f"  target accepted snippets per language: {target_pool_size}\n"
            f"  maximum candidate pool per language: {target_pool_size}"
        )
        for language in languages:
            if args.only_under_target and not bucket_is_undercovered(query["label"], language, undercovered_buckets):
                print(f"  SKIP language={language!r}: this label-language bucket is already at target")
                continue
            print(
                f"  SEARCH language={language!r}: looking for alias {query['query']!r}; "
                f"kept candidates will be assigned to {query['label']}"
            )
            bucket = (query["label"], query["query"], language)
            pool, client = collect_pool_for_bucket(
                client=client,
                date_range_cls=date_range_cls,
                connect_fn=connect_fn,
                query=query,
                search_language=language,
                target_pool_size=target_pool_size,
                page_size=args.page_size,
                max_pages=args.max_pages,
                max_empty_pages=args.max_empty_pages,
                pause=args.pause,
                year_start=args.year_start,
                year_end=args.year_end,
                max_retries=args.max_retries,
                require_matches=require_matches,
                context_source=args.context_source,
                context_chars=args.context_chars,
                existing_sample_pairs=existing_sample_pairs,
                existing_sample_issues=existing_sample_issues,
                rng=rng,
            )
            pools[bucket] = [normalize_radiostation_row(row) for row in pool]
            print(f"  collected pool: {len(pool)}")

    selected, summary = balanced_select(
        pools,
        target_per_bucket=target_pool_size,
        rng=rng,
        max_per_label=args.max_per_label,
        existing_sample_pairs=existing_sample_pairs,
        existing_sample_issues=existing_sample_issues,
    )
    write_jsonl(args.out, selected)
    registry_written = write_sample_registry(args.sample_registry, selected, existing_sample_pairs)
    summary["counts_by_label"] = dict(sorted(Counter(row["candidate_label"] for row in selected).items()))
    summary["counts_by_label_language"] = dict(
        sorted(Counter(f"{row.get('candidate_label')} || {row.get('search_language')}" for row in selected).items())
    )
    summary["counts_by_query"] = dict(sorted(Counter(row["query"] for row in selected).items()))
    summary["counts_by_search_language"] = dict(sorted(Counter(row["search_language"] for row in selected).items()))
    summary["settings"] = {
        "seeds": str(args.seeds),
        "languages": languages,
        "labels": sorted(parse_labels(args.labels) or []),
        "coverage_json": str(args.coverage_json) if args.coverage_json else "",
        "only_under_target": args.only_under_target,
        "undercovered_label_languages": [f"{label} || {language}" for label, language in sorted(undercovered_buckets)],
        "min_missing": args.min_missing,
        "max_queries_per_label": args.max_queries_per_label,
        "year_start": args.year_start,
        "year_end": args.year_end,
        "target_per_query_lang": args.target_per_query_lang,
        "pool_factor": args.pool_factor,
        "page_size": args.page_size,
        "max_pages": args.max_pages,
        "max_empty_pages": args.max_empty_pages,
        "pause": args.pause,
        "random_seed": args.random_seed,
        "shuffle_aliases": args.shuffle_aliases,
        "require_matches": require_matches,
        "context_source": args.context_source,
        "context_chars": args.context_chars,
        "max_per_label": args.max_per_label,
        "sample_registry": str(args.sample_registry),
        "existing_sample_jsonl": [str(path) for path in args.existing_sample_jsonl],
        "existing_issue_jsonl": [str(path) for path in args.existing_issue_jsonl],
        "existing_issue_entity_pairs": len(existing_sample_pairs) - registry_written,
        "existing_newspaper_date_issues": len(existing_sample_issues),
        "registry_pairs_added": registry_written,
        "deduplication": "global_by_existing_dataset_issue_id_then_issue_id_and_candidate_label",
    }
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"rows": len(selected), "output": str(args.out), "summary": str(args.summary_out), "registry_pairs_added": registry_written},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        raise SystemExit(130)
