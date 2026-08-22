from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_LANGUAGES = ["fr", "de", "en"]
DEFAULT_YEAR_START = 1830
DEFAULT_YEAR_END = 2000
DEFAULT_TARGET_PER_QUERY_LANG = 5
DEFAULT_MAX_PER_LABEL = 5
DEFAULT_POOL_FACTOR = 4
DEFAULT_PAGE_SIZE = 10
DEFAULT_MAX_PAGES = 60
DEFAULT_MAX_EMPTY_PAGES = 12
DEFAULT_PAUSE = 1.0
DEFAULT_MAX_RETRIES = 5
DEFAULT_RANDOM_SEED = 42
DEFAULT_CONTEXT_SOURCE = "full-content"
DEFAULT_CONTEXT_CHARS = 256
DEFAULT_SEEDS = Path("resources/newsagency_seeds.json")
DEFAULT_OUT = Path("data/candidates/newsagency_search_snippets.jsonl")
DEFAULT_SUMMARY_OUT = Path("data/candidates/newsagency_search_snippets_summary.json")
DEFAULT_SAMPLE_REGISTRY = Path("data/candidates/sample_entity_pairs.jsonl")


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


def base_document_id(value: Any) -> str:
    return str(value or "").split("#", 1)[0]


def sample_issue_id(value: Any) -> str:
    document_id = base_document_id(value)
    return re.sub(r"-i\d+$", "", document_id)


def enrich_sample_identity(row: dict[str, Any]) -> dict[str, Any]:
    document_id = base_document_id(row.get("source", {}).get("document_id") if isinstance(row.get("source"), dict) else row.get("id"))
    if not document_id:
        document_id = base_document_id(row.get("id"))
    row["sample_document_id"] = document_id
    row["sample_issue_id"] = sample_issue_id(document_id)
    return row


def sample_pair_key(row: dict[str, Any]) -> tuple[str, str]:
    label = str(row.get("candidate_label") or row.get("label") or "")
    issue_id = str(row.get("sample_issue_id") or sample_issue_id(row.get("id")))
    return issue_id, label


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


def strip_match_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def highlighted_surface(value: str) -> str:
    parts = []
    previous_end: int | None = None
    for match in re.finditer(r"<em>(.*?)</em>", value, flags=re.IGNORECASE | re.DOTALL):
        if previous_end is not None:
            connector = value[previous_end : match.start()]
            if connector and not re.search(r"\w", strip_match_html(connector), flags=re.UNICODE):
                parts.append(strip_match_html(connector))
        parts.append(strip_match_html(match.group(1)))
        previous_end = match.end()
    return "".join(parts).strip()


def content_text_from_raw(raw: dict[str, Any]) -> str:
    text = raw.get("text")
    if isinstance(text, dict):
        for field in ("content", "plainText", "text"):
            value = text.get(field)
            if isinstance(value, str) and value.strip():
                return value
    for field in ("content", "text"):
        value = raw.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def find_casefold(value: str, needle: str) -> tuple[int, int] | None:
    if not needle.strip():
        return None
    start = value.casefold().find(needle.casefold())
    if start < 0:
        return None
    return start, start + len(needle)


def find_match_span(content: str, match_html: str, query: str) -> tuple[int, int] | None:
    for needle in (highlighted_surface(match_html), strip_match_html(match_html), query):
        span = find_casefold(content, needle)
        if span:
            return span
    return None


def context_window(content: str, start: int, stop: int, radius: int, *, rng: random.Random | None = None) -> tuple[str, int, int]:
    before = radius
    after = radius
    if rng is not None and radius > 1:
        max_context = radius * 2
        min_context = min(max_context, 100)
        total_context = rng.randint(min_context, max_context)
        min_side = min(radius // 2, total_context // 4)
        min_before = min_side
        max_before = total_context - min_side
        if min_before > max_before:
            min_before = max_before = total_context // 2
        before = rng.randint(min_before, max_before)
        after = total_context - before
    left = max(0, start - before)
    right = min(len(content), stop + after)
    missing_left = before - (start - left)
    missing_right = after - (right - stop)
    if missing_left > 0 and right < len(content):
        right = min(len(content), right + missing_left)
    if missing_right > 0 and left > 0:
        left = max(0, left - missing_right)
    while left > 0 and not content[left - 1].isspace():
        left -= 1
    while right < len(content) and not content[right].isspace():
        right += 1
    return content[left:right].strip(), left, right


def expand_candidate_with_full_content(
    row: dict[str, Any],
    content: str,
    *,
    context_chars: int,
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    matches = row.get("matches")
    if not isinstance(matches, list) or not matches:
        return [row]
    out = []
    base_id = str(row["id"])
    for index, match_html in enumerate(matches):
        match_html = str(match_html)
        match_text = strip_match_html(match_html)
        span = find_match_span(content, match_html, str(row.get("query") or ""))
        revised = dict(row)
        revised["id"] = f"{base_id}#match-{index}"
        revised["source"] = {**dict(row.get("source") or {}), "document_id": base_id}
        revised["match_index"] = index
        revised["match_html"] = match_html
        revised["match_text"] = match_text
        if span:
            start, stop = span
            text, context_start, context_stop = context_window(content, start, stop, context_chars, rng=rng)
            revised["text"] = text
            revised["text_source"] = "full_content_match"
            revised["context_start"] = context_start
            revised["context_stop"] = context_stop
            revised["match_start"] = start
            revised["match_stop"] = stop
        else:
            revised["text"] = match_text
            revised["text_source"] = "match_fragment"
            revised["context_lookup_failed"] = True
        out.append(revised)
    return out


def clean_aliases(row: dict[str, Any], languages: list[str]) -> list[str]:
    aliases: list[str] = []
    search_aliases = row.get("search_aliases") or []
    search_aliases_by_language = row.get("search_aliases_by_language") or {}
    has_search_aliases = bool(search_aliases or search_aliases_by_language)
    alias_fields = [search_aliases] if has_search_aliases else [row.get("aliases") or []]
    for values in alias_fields:
        for value in values:
            if isinstance(value, str) and value.strip():
                aliases.append(value.strip())
    aliases_by_language = search_aliases_by_language or ({} if has_search_aliases else row.get("aliases_by_language") or {})
    if isinstance(aliases_by_language, dict):
        for language in languages:
            values = aliases_by_language.get(language) or []
            for value in values:
                if isinstance(value, str) and value.strip():
                    aliases.append(value.strip())
    if not has_search_aliases and isinstance(row.get("display_name"), str) and row["display_name"].strip():
        aliases.append(row["display_name"].strip())
    seen = set()
    out = []
    for alias in aliases:
        if alias not in seen:
            seen.add(alias)
            out.append(alias)
    return out


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
        if not label.startswith("org.ent.pressagency."):
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


def load_sampling_plan_queries(path: Path, *, family: str = "pressagency", labels: set[str] | None = None) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], int]]:
    if not path.is_file():
        raise SystemExit(f"Sampling plan does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SystemExit(f"Sampling plan has no rows array: {path}")
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    bucket_targets: dict[tuple[str, str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("family") != family:
            continue
        label = str(row.get("label") or "")
        if labels is not None and label not in labels:
            continue
        query = str(row.get("query") or "").strip()
        language = str(row.get("language") or "").strip()
        planned_new = int(row.get("planned_new") or 0)
        if not label or not query or not language or planned_new <= 0:
            continue
        key = (label, query)
        item = grouped.setdefault(
            key,
            {
                "query": query,
                "label": label,
                "canonical_id": str(row.get("canonical_id") or label.rsplit(".", 1)[-1]),
                "display_name": str(row.get("display_name") or query),
                "planned_languages": {},
            },
        )
        item["planned_languages"][language] = planned_new
        bucket_targets[(label, query, language)] = planned_new
    queries = list(grouped.values())
    queries.sort(key=lambda item: (str(item["label"]), str(item["query"]).casefold()))
    return queries, bucket_targets


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
    return enrich_sample_identity(row)


def import_runtime() -> tuple[Any, Any]:
    local_cache = Path("cache.d")
    (local_cache / "matplotlib").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(local_cache))
    os.environ.setdefault("MPLCONFIGDIR", str(local_cache / "matplotlib"))
    try:
        from impresso import DateRange, connect  # type: ignore
    except ImportError as exc:
        raise SystemExit("News-agency sampling requires the impresso package.") from exc
    load_local_env()

    def connect_from_env() -> Any:
        api_url = os.getenv("IMPRESSO_API_URL") or None
        persisted_token = parse_bool(os.getenv("IMPRESSO_PERSISTED_TOKEN"), default=False)
        return connect(public_api_url=api_url, persisted_token=persisted_token)

    return DateRange, connect_from_env


def parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().casefold() in {"1", "true", "yes", "y", "on"}


def load_local_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(".env"))


def is_auth_error(exc: Exception) -> bool:
    text = str(exc).lower()
    status = getattr(exc, "status", None)
    return status == 401 or "401" in text or "unauthorized" in text or "jwt expired" in text


def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    status = getattr(exc, "status", None)
    return status == 429 or "429" in text or "rate limit" in text


class RateLimitThrottle:
    def __init__(
        self,
        *,
        cooldown_seconds: float = 30.0,
        steady_pause_seconds: float = 3.0,
        sleep_fn: Any = time.sleep,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.steady_pause_seconds = steady_pause_seconds
        self.sleep_fn = sleep_fn
        self.enabled = False

    def before_request(self, request_label: str = "request") -> None:
        if self.enabled and self.steady_pause_seconds > 0:
            print(f"rate-limit throttle -> sleeping {self.steady_pause_seconds:.1f}s before {request_label}")
            self.sleep_fn(self.steady_pause_seconds)

    def after_rate_limit(self) -> None:
        if self.cooldown_seconds > 0:
            print(f"rate limit detected -> sleeping {self.cooldown_seconds:.1f}s")
            self.sleep_fn(self.cooldown_seconds)
        if self.steady_pause_seconds > 0 and not self.enabled:
            print(f"rate-limit throttle enabled: {self.steady_pause_seconds:.1f}s between requests")
        self.enabled = True


def sleep_backoff(attempt: int, *, sleep_fn: Any = time.sleep) -> None:
    wait = min(20.0, 2.0**attempt) + 0.2
    print(f"search error -> sleeping {wait:.1f}s")
    sleep_fn(wait)


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
    throttle: RateLimitThrottle | None = None,
) -> tuple[Any, Any]:
    for attempt in range(max_retries):
        try:
            if throttle:
                throttle.before_request(f"search request ({term!r}, {language}, offset={offset})")
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
            if throttle and is_rate_limit_error(exc):
                throttle.after_rate_limit()
                continue
            if is_auth_error(exc):
                print("Authentication problem detected; reconnecting Impresso client...")
                try:
                    client = connect_fn()
                except Exception as reconnect_exc:
                    print(f"Reconnect failed: {reconnect_exc}")
            sleep_backoff(attempt)
    return None, client


def safe_content_text(client: Any, document_id: str, *, throttle: RateLimitThrottle | None = None) -> str:
    try:
        if throttle:
            throttle.before_request(f"full-content request ({document_id})")
        return content_text_from_raw(client.content_items.get(document_id).raw)
    except Exception as exc:
        if throttle and is_rate_limit_error(exc):
            throttle.after_rate_limit()
        raise


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
    context_source: str = "match",
    context_chars: int = DEFAULT_CONTEXT_CHARS,
    existing_sample_pairs: set[tuple[str, str]] | None = None,
    existing_sample_issues: set[str] | None = None,
    rng: random.Random | None = None,
    throttle: RateLimitThrottle | None = None,
) -> tuple[list[dict[str, Any]], Any]:
    pool: list[dict[str, Any]] = []
    seen = set()
    existing_sample_pairs = existing_sample_pairs or set()
    existing_sample_issues = existing_sample_issues or set()
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
            throttle=throttle,
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
            if row is None:
                continue
            enrich_sample_identity(row)
            if row.get("sample_issue_id") in existing_sample_issues:
                continue
            if sample_pair_key(row) in existing_sample_pairs:
                continue
            rows = [row]
            if context_source == "full-content":
                try:
                    content = safe_content_text(client, row["id"], throttle=throttle)
                    if content:
                        rows = expand_candidate_with_full_content(row, content, context_chars=context_chars, rng=rng)
                except Exception as exc:
                    print(f"  full-content context failed for {row['id']}: {exc}")
            elif context_source == "match":
                matches = row.get("matches") or []
                if isinstance(matches, list) and matches:
                    rows = []
                    for match_index, match_html in enumerate(matches):
                        revised = dict(row)
                        revised["id"] = f"{row['id']}#match-{match_index}"
                        revised["source"] = {**dict(row.get("source") or {}), "document_id": row["id"]}
                        revised["match_index"] = match_index
                        revised["match_html"] = str(match_html)
                        revised["match_text"] = strip_match_html(str(match_html))
                        revised["text"] = revised["match_text"]
                        revised["text_source"] = "match_fragment"
                        rows.append(revised)
            elif context_source == "snippet" and row.get("snippet"):
                row["text"] = str(row["snippet"])
                row["text_source"] = "snippet"
            for candidate in rows:
                enrich_sample_identity(candidate)
                if candidate.get("sample_issue_id") in existing_sample_issues:
                    continue
                if candidate["id"] in seen:
                    continue
                seen.add(candidate["id"])
                pool.append(candidate)
                accepted += 1
                if len(pool) >= target_pool_size:
                    break
            if len(pool) >= target_pool_size:
                break
        empty_pages = empty_pages + 1 if accepted == 0 else 0
        offset += page_size
    return pool, client


def balanced_select(
    pools: dict[tuple[str, str, str], list[dict[str, Any]]],
    *,
    target_per_bucket: int,
    target_per_bucket_by_key: dict[tuple[str, str, str], int] | None = None,
    rng: random.Random,
    max_per_label: int,
    existing_sample_pairs: set[tuple[str, str]] | None = None,
    existing_sample_issues: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    del rng
    existing_sample_pairs = existing_sample_pairs or set()
    existing_sample_issues = existing_sample_issues or set()
    bucket_order = list(pools)
    indexes = {bucket: 0 for bucket in bucket_order}
    counts: Counter[tuple[str, str, str]] = Counter()
    counts_by_label: Counter[str] = Counter()
    selected = []
    seen = set(existing_sample_pairs)
    made_progress = True
    while made_progress:
        made_progress = False
        for bucket in bucket_order:
            bucket_target = target_per_bucket_by_key.get(bucket, target_per_bucket) if target_per_bucket_by_key else target_per_bucket
            if counts[bucket] >= bucket_target:
                continue
            label = bucket[0]
            if max_per_label > 0 and counts_by_label[label] >= max_per_label:
                continue
            pool = pools[bucket]
            idx = indexes[bucket]
            while idx < len(pool):
                row = pool[idx]
                idx += 1
                enrich_sample_identity(row)
                if row.get("sample_issue_id") in existing_sample_issues:
                    continue
                dedupe_key = sample_pair_key(row)
                if dedupe_key in seen:
                    continue
                selected.append(row)
                seen.add(dedupe_key)
                counts[bucket] += 1
                counts_by_label[label] += 1
                made_progress = True
                break
            indexes[bucket] = idx
    summary = {
        "total_selected": len(selected),
        "target_per_query_language": target_per_bucket,
        "target_per_label_query_language": {
            f"{label} || {query} || {lang}": (target_per_bucket_by_key.get((label, query, lang), target_per_bucket) if target_per_bucket_by_key else target_per_bucket)
            for label, query, lang in bucket_order
        },
        "counts_by_label_query_language": {f"{label} || {query} || {lang}": counts[(label, query, lang)] for label, query, lang in bucket_order},
        "pool_sizes_by_label_query_language": {f"{label} || {query} || {lang}": len(pools[(label, query, lang)]) for label, query, lang in bucket_order},
        "unfilled_label_query_languages": {
            f"{label} || {query} || {lang}": {
                "selected": counts[(label, query, lang)],
                "target": (target_per_bucket_by_key.get((label, query, lang), target_per_bucket) if target_per_bucket_by_key else target_per_bucket),
                "pool_size": len(pools[(label, query, lang)]),
            }
            for label, query, lang in bucket_order
            if counts[(label, query, lang)] < (target_per_bucket_by_key.get((label, query, lang), target_per_bucket) if target_per_bucket_by_key else target_per_bucket)
        },
        "max_per_label": max_per_label,
        "counts_by_label_selected": dict(sorted(counts_by_label.items())),
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


def load_undercovered_labels(path: Path, *, family: str = "pressagency", min_missing: int = 1) -> set[str]:
    return {label for label, _language in load_undercovered_buckets(path, family=family, min_missing=min_missing)}


def load_undercovered_buckets(path: Path, *, family: str = "pressagency", min_missing: int = 1) -> set[tuple[str, str]]:
    return set(load_undercovered_bucket_missing(path, family=family, min_missing=min_missing))


def load_undercovered_bucket_missing(path: Path, *, family: str = "pressagency", min_missing: int = 1) -> dict[tuple[str, str], int]:
    if not path.is_file():
        raise SystemExit(
            f"Coverage JSON does not exist: {path}\n"
            "Run: make annotation-stats CFG=configs/model-v0.1.0.mk"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SystemExit(f"Coverage JSON has no rows array: {path}")
    buckets: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("family") != family:
            continue
        label = str(row.get("label", ""))
        if not label.startswith("org.ent."):
            continue
        languages = row.get("languages")
        if isinstance(languages, dict) and languages:
            for language, item in languages.items():
                if isinstance(item, dict) and int(item.get("missing_to_target") or 0) >= min_missing:
                    buckets[(label, str(language))] = int(item.get("missing_to_target") or 0)
        elif int(row.get("missing_to_target") or 0) >= min_missing:
            buckets[(label, "*")] = int(row.get("missing_to_target") or 0)
    return buckets


def bucket_is_undercovered(label: str, language: str, undercovered_buckets: set[tuple[str, str]]) -> bool:
    return (label, language) in undercovered_buckets or (label, "*") in undercovered_buckets


def missing_for_bucket(label: str, language: str, undercovered_missing: dict[tuple[str, str], int]) -> int | None:
    if (label, language) in undercovered_missing:
        return undercovered_missing[(label, language)]
    if (label, "*") in undercovered_missing:
        return undercovered_missing[(label, "*")]
    return None


def filter_buckets_for_labels(buckets: set[tuple[str, str]], labels: set[str] | None) -> set[tuple[str, str]]:
    if labels is None:
        return buckets
    return {bucket for bucket in buckets if bucket[0] in labels}


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_number}: invalid JSONL row: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def load_sample_pairs(paths: list[Path]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for path in paths:
        for row in iter_jsonl(path):
            label = str(row.get("label") or row.get("candidate_label") or "")
            issue_id = str(row.get("sample_issue_id") or row.get("issue_id") or "")
            if not issue_id:
                document_id = row.get("sample_document_id")
                if not document_id and isinstance(row.get("source"), dict):
                    document_id = row["source"].get("document_id")
                if not document_id:
                    document_id = row.get("id")
                issue_id = sample_issue_id(document_id)
            if label and issue_id:
                pairs.add((issue_id, label))
    return pairs


def load_sample_issues(paths: list[Path]) -> set[str]:
    issues: set[str] = set()
    for path in paths:
        for row in iter_jsonl(path):
            issue_id = str(row.get("sample_issue_id") or row.get("issue_id") or "")
            if not issue_id:
                document_id = row.get("sample_document_id")
                if not document_id and isinstance(row.get("legacy"), dict):
                    document_id = row["legacy"].get("source_document_id") or row["legacy"].get("source_id")
                if not document_id and isinstance(row.get("source"), dict):
                    document_id = row["source"].get("document_id")
                if not document_id:
                    document_id = row.get("document_id") or row.get("id")
                issue_id = sample_issue_id(document_id)
            if issue_id:
                issues.add(issue_id)
    return issues


def write_sample_registry(path: Path, rows: list[dict[str, Any]], existing_pairs: set[tuple[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            enrich_sample_identity(row)
            pair = sample_pair_key(row)
            if pair in existing_pairs:
                continue
            payload = {
                "label": pair[1],
                "sample_issue_id": pair[0],
                "sample_document_id": row.get("sample_document_id"),
                "sample_id": row.get("id"),
                "query": row.get("query"),
                "search_language": row.get("search_language"),
                "date": row.get("date"),
                "mediaId": row.get("mediaId"),
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            existing_pairs.add(pair)
            written += 1
    return written


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Balanced Impresso sampler for news-agency search-result snippets.")
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    parser.add_argument("--languages", nargs="+", default=DEFAULT_LANGUAGES)
    parser.add_argument("--labels", default="", help="Optional whitespace-separated canonical labels to sample.")
    parser.add_argument("--coverage-json", type=Path, help="Annotation coverage JSON from make annotation-stats.")
    parser.add_argument("--sampling-plan", type=Path, help="Focused sampling plan JSON from make plan-media-sampling.")
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
    parser.add_argument("--rate-limit-cooldown", type=float, default=30.0, help="Seconds to sleep immediately after an HTTP 429/rate-limit response.")
    parser.add_argument("--rate-limit-pause", type=float, default=3.0, help="Seconds to sleep before each later request after the first 429/rate-limit response.")
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
    undercovered_missing: dict[tuple[str, str], int] = {}
    if args.only_under_target:
        if not args.coverage_json:
            raise SystemExit("--only-under-target requires --coverage-json")
        undercovered_missing = load_undercovered_bucket_missing(args.coverage_json, min_missing=args.min_missing)
        undercovered_buckets = set(undercovered_missing)
        undercovered = {label for label, _language in undercovered_buckets}
        labels = undercovered if labels is None else labels & undercovered
    reported_undercovered_buckets = filter_buckets_for_labels(undercovered_buckets, labels)
    rng = random.Random(args.random_seed) if args.random_seed is not None else random.Random()
    alias_rng = (random.Random(args.random_seed) if args.random_seed is not None else random.Random()) if args.shuffle_aliases else None
    sampling_plan_targets: dict[tuple[str, str, str], int] = {}
    if args.sampling_plan:
        queries, sampling_plan_targets = load_sampling_plan_queries(args.sampling_plan, family="pressagency", labels=labels)
    else:
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
    throttle = RateLimitThrottle(cooldown_seconds=args.rate_limit_cooldown, steady_pause_seconds=args.rate_limit_pause)
    require_matches = not args.allow_snippet_only
    pools: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    bucket_targets: dict[tuple[str, str, str], int] = {}
    interrupted = False
    interrupted_at = ""
    try:
        for query in queries:
            print(f"\n=== QUERY: {query['query']} [{query['label']}] ===")
            for language in languages:
                if args.sampling_plan:
                    planned_languages = query.get("planned_languages") or {}
                    if language not in planned_languages:
                        continue
                if args.only_under_target and not bucket_is_undercovered(query["label"], language, undercovered_buckets):
                    continue
                bucket = (query["label"], query["query"], language)
                if args.sampling_plan:
                    bucket_target = sampling_plan_targets[bucket]
                else:
                    missing = missing_for_bucket(query["label"], language, undercovered_missing) if args.only_under_target else None
                    bucket_target = min(args.target_per_query_lang, missing) if missing is not None else args.target_per_query_lang
                bucket_targets[bucket] = bucket_target
                target_pool_size = bucket_target * args.pool_factor
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
                pools[bucket] = pool
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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user before sampler output could be finalized.", file=sys.stderr)
        raise SystemExit(130)
