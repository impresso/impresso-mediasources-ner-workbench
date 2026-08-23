from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from typing import Any, Callable


SUPPORTED_FAMILIES = {"pressagency", "radiostation"}

LoadSeedQueries = Callable[..., list[dict[str, str]]]
NormalizeRow = Callable[[dict[str, Any]], dict[str, Any]]


def identity_row(row: dict[str, Any]) -> dict[str, Any]:
    return row


def run_family_sampler(
    args: argparse.Namespace,
    *,
    family: str,
    load_seed_queries: LoadSeedQueries,
    normalize_row: NormalizeRow = identity_row,
    verbose_alias_header: bool = False,
) -> int:
    from .sample_newsagencies import (
        RateLimitThrottle,
        balanced_select,
        bucket_is_undercovered,
        collect_pool_for_bucket,
        filter_buckets_for_labels,
        import_runtime,
        load_sample_issues,
        load_sample_pairs,
        load_sampling_plan_queries,
        load_undercovered_bucket_missing,
        missing_for_bucket,
        parse_labels,
        successful_alias_limit_reached,
        write_jsonl,
        write_sample_registry,
    )

    languages = [language.strip() for language in args.languages if language.strip()]
    labels = parse_labels(args.labels)
    undercovered_buckets: set[tuple[str, str]] = set()
    undercovered_missing: dict[tuple[str, str], int] = {}
    if args.only_under_target:
        if not args.coverage_json:
            raise SystemExit("--only-under-target requires --coverage-json")
        undercovered_missing = load_undercovered_bucket_missing(args.coverage_json, family=family, min_missing=args.min_missing)
        undercovered_buckets = set(undercovered_missing)
        undercovered = {label for label, _language in undercovered_buckets}
        labels = undercovered if labels is None else labels & undercovered
    reported_undercovered_buckets = filter_buckets_for_labels(undercovered_buckets, labels)
    rng = random.Random(args.random_seed) if args.random_seed is not None else random.Random()
    alias_rng = (random.Random(args.random_seed) if args.random_seed is not None else random.Random()) if args.shuffle_aliases else None
    sampling_plan_targets: dict[tuple[str, str, str], int] = {}
    if args.sampling_plan:
        queries, sampling_plan_targets = load_sampling_plan_queries(args.sampling_plan, family=family, labels=labels)
    else:
        queries = load_seed_queries(
            args.seeds,
            languages=languages,
            labels=labels,
            max_queries_per_label=args.max_queries_per_label,
            rng=alias_rng,
        )
    if alias_rng is not None:
        alias_rng.shuffle(queries)
    print("Seed file:", args.seeds)
    print("Queries:", len(queries))
    print("Languages:", languages)
    if args.only_under_target:
        print("Under-target labels:", len(labels or []))
        print("Under-target label-language buckets:", len(reported_undercovered_buckets))
    print("Output:", args.out)
    if args.sampling_plan:
        print("Sampling plan:", args.sampling_plan)
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
    throttle = RateLimitThrottle(
        cooldown_seconds=getattr(args, "rate_limit_cooldown", 0.0),
        steady_pause_seconds=getattr(args, "rate_limit_pause", 0.0),
    )
    require_matches = not args.allow_snippet_only
    pools: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    bucket_targets: dict[tuple[str, str, str], int] = {}
    successful_aliases: Counter[tuple[str, str]] = Counter()
    interrupted = False
    interrupted_at = ""
    try:
        for query in queries:
            if verbose_alias_header:
                print(
                    f"\n=== ALIAS SEARCH: {query['query']!r} ===\n"
                    f"  canonical label: {query['label']}\n"
                    f"  canonical id: {query['canonical_id']}\n"
                    f"  display name: {query['display_name']}"
                )
            else:
                print(f"\n=== QUERY: {query['query']} [{query['label']}] ===")
            for language in languages:
                if args.sampling_plan:
                    planned_languages = query.get("planned_languages") or {}
                    if language not in planned_languages:
                        continue
                if args.only_under_target and not bucket_is_undercovered(query["label"], language, undercovered_buckets):
                    if verbose_alias_header:
                        print(f"  SKIP language={language!r}: this label-language bucket is already at target")
                    continue
                if successful_alias_limit_reached(
                    successful_aliases,
                    label=query["label"],
                    language=language,
                    max_queries_per_label=args.max_queries_per_label,
                ):
                    prefix = "SKIP" if verbose_alias_header else "skip"
                    print(
                        f"  {prefix} lang={language!r}: already found non-empty pools for "
                        f"{args.max_queries_per_label} alias(es) for this label/language"
                    )
                    continue
                bucket = (query["label"], query["query"], language)
                if args.sampling_plan:
                    bucket_target = sampling_plan_targets[bucket]
                else:
                    missing = missing_for_bucket(query["label"], language, undercovered_missing) if args.only_under_target else None
                    bucket_target = min(args.target_per_query_lang, missing) if missing is not None else args.target_per_query_lang
                bucket_targets[bucket] = bucket_target
                target_pool_size = bucket_target * args.pool_factor
                if verbose_alias_header:
                    print(
                        f"  SEARCH language={language!r}: looking for alias {query['query']!r}; "
                        f"target={bucket_target}, pool={target_pool_size}; kept candidates will be assigned to {query['label']}"
                    )
                interrupted_at = f"{query['label']} || {query['query']} || {language}"
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
                    throttle=throttle,
                )
                pools[bucket] = [normalize_row(row) for row in pool]
                if pool:
                    successful_aliases[(query["label"], language)] += 1
                print(f"  collected pool: {len(pool)}")
                interrupted_at = ""
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted by user; writing output from completed sampling buckets.", file=sys.stderr)

    selected, summary = balanced_select(
        pools,
        target_per_bucket=args.target_per_query_lang,
        target_per_bucket_by_key=bucket_targets,
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
    summary["successful_aliases_by_label_language"] = {
        f"{label} || {language}": count for (label, language), count in sorted(successful_aliases.items())
    }
    summary["settings"] = {
        "seeds": str(args.seeds),
        "languages": languages,
        "labels": sorted(parse_labels(args.labels) or []),
        "coverage_json": str(args.coverage_json) if args.coverage_json else "",
        "sampling_plan": str(args.sampling_plan) if args.sampling_plan else "",
        "only_under_target": args.only_under_target,
        "undercovered_label_languages": [f"{label} || {language}" for label, language in sorted(reported_undercovered_buckets)],
        "min_missing": args.min_missing,
        "max_queries_per_label": args.max_queries_per_label,
        "year_start": args.year_start,
        "year_end": args.year_end,
        "target_per_query_lang": args.target_per_query_lang,
        "target_per_query_lang_coverage_aware": args.only_under_target,
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
    summary["interrupted"] = interrupted
    summary["interrupted_at"] = interrupted_at
    summary["completed_pool_buckets"] = len(pools)
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


def split_family(argv: list[str] | None) -> tuple[str, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--family", choices=sorted(SUPPORTED_FAMILIES), required=True)
    args, rest = parser.parse_known_args(argv)
    return args.family, rest


def main(argv: list[str] | None = None) -> int:
    family, rest = split_family(argv)
    if family == "pressagency":
        from .sample_newsagencies import main as family_main

        return family_main(rest)
    if family == "radiostation":
        from .sample_radiostations import main as family_main

        return family_main(rest)
    raise SystemExit(f"unsupported media-source family for sampling: {family}")


if __name__ == "__main__":
    raise SystemExit(main())
