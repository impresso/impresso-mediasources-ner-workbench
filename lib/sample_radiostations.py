from __future__ import annotations

import argparse
import json
import random
import sys
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
    clean_aliases,
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
    parser.add_argument("--sampling-plan", type=Path, help="Focused sampling plan JSON from make plan-media-sampling.")
    parser.add_argument("--only-under-target", action="store_true", help="Only sample labels still below the target in --coverage-json.")
    parser.add_argument("--min-missing", type=int, default=1, help="Minimum missing_to_target needed when --only-under-target is set.")
    parser.add_argument(
        "--max-queries-per-label",
        type=int,
        default=3,
        help="Maximum non-empty alias searches to keep per label/language; empty-result aliases do not consume this limit. Use 0 for no limit.",
    )
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
    parser.add_argument("--shuffle-aliases", action=argparse.BooleanOptionalAction, default=True, help="Shuffle alias search order; enabled by default.")
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
    from .sample_media_snippets import run_family_sampler

    return run_family_sampler(
        parse_args(argv),
        family="radiostation",
        load_seed_queries=load_seed_queries,
        normalize_row=normalize_radiostation_row,
        verbose_alias_header=True,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        raise SystemExit(130)
