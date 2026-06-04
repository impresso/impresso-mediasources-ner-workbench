from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_LANGUAGES = ["fr", "de", "en"]
DEFAULT_YEAR_START = 1830
DEFAULT_YEAR_END = 2000
DEFAULT_TARGET_PER_QUERY_LANG = 10
DEFAULT_POOL_FACTOR = 4
DEFAULT_PAGE_SIZE = 10
DEFAULT_MAX_PAGES = 60
DEFAULT_MAX_EMPTY_PAGES = 12
DEFAULT_PAUSE = 1.0
DEFAULT_MAX_RETRIES = 5
DEFAULT_RANDOM_SEED = 42
DEFAULT_SEEDS = Path("resources/newsagency_seeds.json")
DEFAULT_OUT = Path("data/candidates/newsagency_search_snippets.jsonl")
DEFAULT_SUMMARY_OUT = Path("data/candidates/newsagency_search_snippets_summary.json")


def first_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def normalize_id(hit: dict[str, Any]) -> str | None:
    return first_str(
        hit.get("id"),
        hit.get("uid"),
        hit.get("contentItemId"),
        hit.get("content_item_id"),
    )


def extract_matches(hit: dict[str, Any]) -> list[str]:
    matches: list[str] = []
    text = hit.get("text") or {}
    raw_matches = text.get("matches") if isinstance(text, dict) else None
    if raw_matches is None:
        raw_matches = hit.get("matches")
    if not isinstance(raw_matches, list):
        return matches
    for match in raw_matches:
        fragment = None
        if isinstance(match, dict):
            fragment = first_str(match.get("fragment"), match.get("text"), match.get("snippet"))
        elif isinstance(match, str):
            fragment = match.strip()
        if fragment:
            matches.append(fragment)
    return matches


def clean_aliases(row: dict[str, Any], languages: list[str]) -> list[str]:
    aliases: list[str] = []
    for value in row.get("aliases") or []:
        if isinstance(value, str) and value.strip():
            aliases.append(value.strip())
    aliases_by_language = row.get("aliases_by_language") or {}
    if isinstance(aliases_by_language, dict):
        for language in languages:
            values = aliases_by_language.get(language) or []
            for value in values:
                if isinstance(value, str) and value.strip():
                    aliases.append(value.strip())
    if isinstance(row.get("display_name"), str) and row["display_name"].strip():
        aliases.append(row["display_name"].strip())
    seen = set()
    out = []
    for alias in aliases:
        if alias not in seen:
            seen.add(alias)
            out.append(alias)
    return out


def load_seed_queries(path: Path, *, languages: list[str], labels: set[str] | None, max_queries_per_label: int) -> list[dict[str, str]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    queries: list[dict[str, str]] = []
    for row in rows:
        label = str(row.get("label", ""))
        if not label.startswith("org.ent.pressagency."):
            continue
        if labels is not None and label not in labels:
            continue
        if row.get("trainable") is False:
            continue
        aliases = clean_aliases(row, languages)
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


def extract_candidate(
    hit: dict[str, Any],
    *,
    query: dict[str, str],
    search_language: str,
    require_matches: bool,
) -> dict[str, Any] | None:
    item_id = normalize_id(hit)
    if not item_id:
        return None
    text = hit.get("text") or {}
    meta = hit.get("meta") or {}
    matches = extract_matches(hit)
    snippet = None
    actual_language = search_language
    if isinstance(text, dict):
        snippet = first_str(text.get("snippet"))
        actual_language = first_str(text.get("langCode"), search_language) or search_language
    if require_matches and not matches:
        return None
    if not snippet and not matches:
        return None

    row = {
        "id": item_id,
        "label": query["label"],
        "candidate_label": query["label"],
        "agency": query["canonical_id"],
        "agency_name": query["display_name"],
        "query": query["query"],
        "search_language": search_language,
        "language": actual_language,
        "matches": matches,
        "source": {
            "type": "impresso_search_result",
            "document_id": item_id,
        },
    }
    if snippet:
        row["snippet"] = snippet
    if isinstance(meta, dict):
        for field in (
            "date",
            "mediaId",
            "mediaTitle",
            "document_type",
            "item_type",
            "ocrQuality",
            "access_domain",
            "copyright",
            "page_id",
            "iiif_manifest",
            "iiif_thumbnail",
        ):
            if field in meta:
                row[field] = meta[field]
    return row


def import_runtime() -> tuple[Any, Any]:
    try:
        from impresso import DateRange, connect  # type: ignore
    except ImportError as exc:
        raise SystemExit("News-agency sampling requires the impresso package.") from exc
    return DateRange, connect


def is_auth_error(exc: Exception) -> bool:
    text = str(exc).lower()
    status = getattr(exc, "status", None)
    return status == 401 or "401" in text or "unauthorized" in text or "jwt expired" in text


def sleep_backoff(attempt: int) -> None:
    wait = min(20.0, 2.0**attempt) + 0.2
    print(f"search error -> sleeping {wait:.1f}s")
    time.sleep(wait)


def safe_search(
    *,
    client: Any,
    date_range_cls: Any,
    term: str,
    language: str,
    offset: int,
    limit: int,
    year_start: int,
    year_end: int,
    max_retries: int,
    connect_fn: Any,
) -> tuple[Any, Any]:
    for attempt in range(max_retries):
        try:
            result = client.search.find(
                term=term,
                language=language,
                date_range=date_range_cls(f"{year_start}-01-01", f"{year_end}-12-31"),
                with_text_contents=True,
                limit=limit,
                offset=offset,
            )
            return result, client
        except Exception as exc:
            print(f"search failed ({term!r}, {language}, offset={offset}) attempt {attempt + 1}/{max_retries}: {exc}")
            if is_auth_error(exc):
                print("Authentication problem detected; reconnecting Impresso client...")
                try:
                    client = connect_fn()
                except Exception as reconnect_exc:
                    print(f"Reconnect failed: {reconnect_exc}")
            sleep_backoff(attempt)
    return None, client


def collect_pool_for_bucket(
    *,
    client: Any,
    date_range_cls: Any,
    connect_fn: Any,
    query: dict[str, str],
    search_language: str,
    target_pool_size: int,
    page_size: int,
    max_pages: int,
    max_empty_pages: int,
    pause: float,
    year_start: int,
    year_end: int,
    max_retries: int,
    require_matches: bool,
) -> tuple[list[dict[str, Any]], Any]:
    pool: list[dict[str, Any]] = []
    seen = set()
    offset = 0
    pages_seen = 0
    empty_pages = 0
    while len(pool) < target_pool_size and pages_seen < max_pages and empty_pages < max_empty_pages:
        print(f"  search query={query['query']!r} lang={search_language} offset={offset} pool={len(pool)}/{target_pool_size}")
        result, client = safe_search(
            client=client,
            date_range_cls=date_range_cls,
            term=query["query"],
            language=search_language,
            offset=offset,
            limit=page_size,
            year_start=year_start,
            year_end=year_end,
            max_retries=max_retries,
            connect_fn=connect_fn,
        )
        time.sleep(pause)
        pages_seen += 1
        if result is None:
            break
        raw = getattr(result, "raw", None)
        if not isinstance(raw, dict):
            break
        hits = raw.get("data", [])
        if not hits:
            break
        accepted = 0
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            row = extract_candidate(hit, query=query, search_language=search_language, require_matches=require_matches)
            if row is None or row["id"] in seen:
                continue
            seen.add(row["id"])
            pool.append(row)
            accepted += 1
            if len(pool) >= target_pool_size:
                break
        empty_pages = empty_pages + 1 if accepted == 0 else 0
        offset += page_size
    return pool, client


def balanced_select(
    pools: dict[tuple[str, str, str], list[dict[str, Any]]],
    *,
    target_per_bucket: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    for pool in pools.values():
        rng.shuffle(pool)
    bucket_order = list(pools)
    indexes = {bucket: 0 for bucket in bucket_order}
    counts: Counter[tuple[str, str, str]] = Counter()
    selected = []
    seen = set()
    made_progress = True
    while made_progress:
        made_progress = False
        for bucket in bucket_order:
            if counts[bucket] >= target_per_bucket:
                continue
            pool = pools[bucket]
            idx = indexes[bucket]
            while idx < len(pool):
                row = pool[idx]
                idx += 1
                dedupe_key = (row["id"], row["candidate_label"])
                if dedupe_key in seen:
                    continue
                selected.append(row)
                seen.add(dedupe_key)
                counts[bucket] += 1
                made_progress = True
                break
            indexes[bucket] = idx
    summary = {
        "total_selected": len(selected),
        "target_per_query_language": target_per_bucket,
        "counts_by_label_query_language": {f"{label} || {query} || {lang}": counts[(label, query, lang)] for label, query, lang in bucket_order},
        "pool_sizes_by_label_query_language": {f"{label} || {query} || {lang}": len(pools[(label, query, lang)]) for label, query, lang in bucket_order},
        "unfilled_label_query_languages": {
            f"{label} || {query} || {lang}": {
                "selected": counts[(label, query, lang)],
                "target": target_per_bucket,
                "pool_size": len(pools[(label, query, lang)]),
            }
            for label, query, lang in bucket_order
            if counts[(label, query, lang)] < target_per_bucket
        },
    }
    return selected, summary


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_labels(raw: str) -> set[str] | None:
    labels = {item.strip() for item in raw.split() if item.strip()}
    return labels or None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Balanced Impresso sampler for news-agency search-result snippets.")
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    parser.add_argument("--languages", nargs="+", default=DEFAULT_LANGUAGES)
    parser.add_argument("--labels", default="", help="Optional whitespace-separated canonical labels to sample.")
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
    parser.add_argument("--random-seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--allow-snippet-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    languages = [language.strip() for language in args.languages if language.strip()]
    queries = load_seed_queries(args.seeds, languages=languages, labels=parse_labels(args.labels), max_queries_per_label=args.max_queries_per_label)
    print("Seed file:", args.seeds)
    print("Queries:", len(queries))
    print("Languages:", languages)
    print("Output:", args.out)
    if args.dry_run:
        for query in queries[:50]:
            print(f"  {query['label']} || {query['query']}")
        if len(queries) > 50:
            print(f"  ... {len(queries) - 50} more")
        return 0

    date_range_cls, connect_fn = import_runtime()
    client = connect_fn()
    rng = random.Random(args.random_seed)
    require_matches = not args.allow_snippet_only
    target_pool_size = args.target_per_query_lang * args.pool_factor
    pools: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for query in queries:
        print(f"\n=== QUERY: {query['query']} [{query['label']}] ===")
        for language in languages:
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
            )
            pools[bucket] = pool
            print(f"  collected pool: {len(pool)}")

    selected, summary = balanced_select(pools, target_per_bucket=args.target_per_query_lang, rng=rng)
    summary["counts_by_label"] = dict(sorted(Counter(row["candidate_label"] for row in selected).items()))
    summary["counts_by_query"] = dict(sorted(Counter(row["query"] for row in selected).items()))
    summary["counts_by_search_language"] = dict(sorted(Counter(row["search_language"] for row in selected).items()))
    summary["settings"] = {
        "seeds": str(args.seeds),
        "languages": languages,
        "labels": sorted(parse_labels(args.labels) or []),
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
        "require_matches": require_matches,
        "deduplication": "global_by_content_item_id_and_candidate_label",
    }
    write_jsonl(args.out, selected)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(selected), "output": str(args.out), "summary": str(args.summary_out)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        raise SystemExit(130)
