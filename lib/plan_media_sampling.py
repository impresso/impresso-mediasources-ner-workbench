from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


GENERIC_TERMS = {
    "agence",
    "agency",
    "agentie",
    "agentur",
    "nachrichtenagentur",
    "presse",
    "press",
    "radio",
    "stampa",
    "telegraph",
    "telegraphen",
    "telegraphique",
    "telegrafica",
}


def normalize_surface(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def surface_tokens(value: str) -> list[str]:
    return [token.casefold() for token in re.findall(r"[\wÀ-ÿ]+", value, flags=re.UNICODE)]


def is_generic_risk(value: str) -> bool:
    tokens = surface_tokens(value)
    if not tokens:
        return True
    distinctive = [token for token in tokens if token not in GENERIC_TERMS]
    return not distinctive


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def family_for_label(label: str) -> str:
    if ".pressagency." in label:
        return "pressagency"
    if ".radiostation." in label:
        return "radiostation"
    if ".newspaper." in label:
        return "newspaper"
    return ""


def row_label(row: dict[str, Any]) -> str:
    return str(row.get("candidate_label") or row.get("label") or "")


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("search_language") or row.get("language") or "")


def count_pending(paths: list[Path], *, family: str) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    seen: set[tuple[str, str, str]] = set()
    for path in paths:
        for row in load_jsonl(path):
            label = row_label(row)
            if family_for_label(label) != family:
                continue
            status = str(row.get("status") or row.get("decision") or "")
            if status in {"rejected", "removed"}:
                continue
            language = row_language(row)
            if not language:
                continue
            row_id = str(row.get("id") or row.get("document_id") or "")
            key = (row_id, label, language)
            if key in seen:
                continue
            seen.add(key)
            counts[(label, language)] += 1
    return counts


def load_coverage(path: Path, *, family: str, min_missing: int) -> dict[tuple[str, str], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SystemExit(f"Coverage JSON has no rows array: {path}")
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("family") != family:
            continue
        label = str(row.get("label") or "")
        languages = row.get("languages")
        if not isinstance(languages, dict):
            continue
        for language, item in languages.items():
            if not isinstance(item, dict):
                continue
            missing = int(item.get("missing_to_target") or 0)
            if missing >= min_missing:
                out[(label, str(language))] = {
                    "missing": missing,
                    "target": int(item.get("target") or 0),
                    "total": int(item.get("total") or 0),
                    "dataset": int(item.get("dataset") or 0),
                }
    return out


def load_profiles(path: Path) -> dict[str, dict[str, dict[str, int]]]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles = payload.get("profiles") if isinstance(payload, dict) else None
    if not isinstance(profiles, list):
        return {}
    out: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        label = str(profile.get("label") or "")
        for surface in profile.get("top_surfaces") or []:
            if not isinstance(surface, dict):
                continue
            normalized = str(surface.get("normalized_surface") or "")
            languages = surface.get("languages") or {}
            if not normalized or not isinstance(languages, dict):
                continue
            for language, count in languages.items():
                out[label][normalized][str(language)] = int(count or 0)
    return out


def alias_entries(seed: dict[str, Any], languages: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(alias: str, language: str) -> None:
        alias = alias.strip()
        if not alias:
            return
        key = (alias, language)
        if key in seen:
            return
        seen.add(key)
        entries.append({"query": alias, "language": language})

    search_aliases = seed.get("search_aliases") or []
    search_aliases_by_language = seed.get("search_aliases_by_language") or {}
    has_search_aliases = bool(search_aliases or search_aliases_by_language)
    base_aliases = search_aliases if has_search_aliases else seed.get("aliases") or []
    for alias in base_aliases:
        if isinstance(alias, str):
            for language in languages:
                add(alias, language)

    by_language = search_aliases_by_language or ({} if has_search_aliases else seed.get("aliases_by_language"))
    if isinstance(by_language, dict):
        for language in languages:
            for alias in by_language.get(language) or []:
                if isinstance(alias, str):
                    add(alias, language)

    display_name = seed.get("display_name")
    if not has_search_aliases and isinstance(display_name, str):
        for language in languages:
            add(display_name, language)
    return entries


def planned_rows(
    *,
    seeds_path: Path,
    coverage_path: Path,
    profiles_path: Path,
    pending_paths: list[Path],
    family: str,
    languages: list[str],
    labels: set[str] | None,
    max_queries_per_bucket: int,
    target_per_bucket: int,
    max_per_label: int,
    min_missing: int,
    surface_saturation: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seeds = json.loads(seeds_path.read_text(encoding="utf-8"))
    coverage = load_coverage(coverage_path, family=family, min_missing=min_missing)
    profiles = load_profiles(profiles_path)
    pending = count_pending(pending_paths, family=family)
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    planned_by_label: Counter[str] = Counter()

    for seed in seeds:
        if not isinstance(seed, dict) or seed.get("trainable") is False:
            continue
        label = str(seed.get("label") or "")
        if family_for_label(label) != family:
            continue
        if labels is not None and label not in labels:
            continue
        canonical_id = str(seed.get("canonical_id") or label.rsplit(".", 1)[-1])
        display_name = str(seed.get("display_name") or canonical_id)
        aliases = alias_entries(seed, languages)
        for language in languages:
            bucket = coverage.get((label, language))
            if not bucket:
                continue
            pending_count = pending[(label, language)]
            missing_after_pending = max(0, int(bucket["missing"]) - pending_count)
            if missing_after_pending <= 0:
                skipped.append(
                    {
                        "label": label,
                        "language": language,
                        "reason": "pending_work_fills_gap",
                        "missing": bucket["missing"],
                        "pending": pending_count,
                    }
                )
                continue
            if max_per_label > 0 and planned_by_label[label] >= max_per_label:
                skipped.append(
                    {
                        "label": label,
                        "language": language,
                        "reason": "max_per_label_already_planned",
                        "missing": bucket["missing"],
                        "pending": pending_count,
                    }
                )
                continue
            candidates = [entry for entry in aliases if entry["language"] == language]
            ranked: list[dict[str, Any]] = []
            for entry in candidates:
                normalized = normalize_surface(entry["query"])
                surface_count = profiles.get(label, {}).get(normalized, {}).get(language, 0)
                generic_risk = is_generic_risk(entry["query"])
                represented = surface_count >= surface_saturation
                if generic_risk:
                    priority = 20
                    reason = "generic_risk"
                elif represented:
                    priority = 60
                    reason = "represented_surface"
                else:
                    priority = 100
                    reason = "underrepresented_surface"
                ranked.append(
                    {
                        "query": entry["query"],
                        "normalized_query": normalized,
                        "surface_count": surface_count,
                        "generic_risk": generic_risk,
                        "priority": priority,
                        "reason": reason,
                    }
                )
            ranked.sort(key=lambda item: (-int(item["priority"]), int(item["surface_count"]), item["query"].casefold()))
            useful = [item for item in ranked if not item["generic_risk"]]
            selected = useful[:max_queries_per_bucket] if useful else ranked[:max_queries_per_bucket]
            if not selected:
                skipped.append(
                    {
                        "label": label,
                        "language": language,
                        "reason": "no_query_alias",
                        "missing": bucket["missing"],
                        "pending": pending_count,
                    }
                )
                continue
            for item in selected:
                if max_per_label > 0 and planned_by_label[label] >= max_per_label:
                    break
                planned_new = min(target_per_bucket, missing_after_pending, max_per_label - planned_by_label[label] if max_per_label > 0 else target_per_bucket)
                if planned_new <= 0:
                    break
                planned_by_label[label] += planned_new
                rows.append(
                    {
                        "family": family,
                        "label": label,
                        "canonical_id": canonical_id,
                        "display_name": display_name,
                        "language": language,
                        "query": item["query"],
                        "normalized_query": item["normalized_query"],
                        "missing": int(bucket["missing"]),
                        "pending": pending_count,
                        "planned_new": planned_new,
                        "target": int(bucket["target"]),
                        "current_total": int(bucket["total"]),
                        "surface_count": int(item["surface_count"]),
                        "priority": int(item["priority"]),
                        "reason": item["reason"],
                    }
                )
    rows.sort(key=lambda item: (-int(item["priority"]), item["label"], item["language"], item["query"].casefold()))
    return rows, skipped


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "family",
        "label",
        "language",
        "query",
        "missing",
        "pending",
        "planned_new",
        "surface_count",
        "reason",
        "priority",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_labels(value: str) -> set[str] | None:
    labels = {item.strip() for item in value.split() if item.strip()}
    return labels or None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan focused media-source sampling from coverage, pending work, and mention surfaces.")
    parser.add_argument("--family", choices=["pressagency", "radiostation"], required=True)
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--profiles-json", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--tsv-output", type=Path, required=True)
    parser.add_argument("--languages", nargs="+", required=True)
    parser.add_argument("--labels", default="")
    parser.add_argument("--pending-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--max-queries-per-bucket", type=int, default=1)
    parser.add_argument("--target-per-bucket", type=int, default=2)
    parser.add_argument("--max-per-label", type=int, default=5)
    parser.add_argument("--min-missing", type=int, default=1)
    parser.add_argument("--surface-saturation", type=int, default=5)
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print(f"Ignoring sampler-only arguments while planning: {' '.join(unknown)}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows, skipped = planned_rows(
        seeds_path=args.seeds,
        coverage_path=args.coverage_json,
        profiles_path=args.profiles_json,
        pending_paths=args.pending_jsonl,
        family=args.family,
        languages=[language for language in args.languages if language],
        labels=parse_labels(args.labels),
        max_queries_per_bucket=args.max_queries_per_bucket,
        target_per_bucket=args.target_per_bucket,
        max_per_label=args.max_per_label,
        min_missing=args.min_missing,
        surface_saturation=args.surface_saturation,
    )
    payload = {
        "family": args.family,
        "rows": rows,
        "skipped": skipped,
        "settings": {
            "seeds": str(args.seeds),
            "coverage_json": str(args.coverage_json),
            "profiles_json": str(args.profiles_json),
            "languages": args.languages,
            "labels": sorted(parse_labels(args.labels) or []),
            "pending_jsonl": [str(path) for path in args.pending_jsonl],
            "max_queries_per_bucket": args.max_queries_per_bucket,
            "target_per_bucket": args.target_per_bucket,
            "max_per_label": args.max_per_label,
            "min_missing": args.min_missing,
            "surface_saturation": args.surface_saturation,
        },
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_tsv(args.tsv_output, rows)
    print(
        json.dumps(
            {
                "family": args.family,
                "planned_queries": len(rows),
                "planned_samples": sum(int(row["planned_new"]) for row in rows),
                "skipped": len(skipped),
                "json": str(args.json_output),
                "tsv": str(args.tsv_output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if rows:
        print("Top planned searches:")
        for row in rows[:20]:
            print(
                f"  {row['label']} {row['language']} planned={row['planned_new']} "
                f"missing={row['missing']} pending={row['pending']} query={row['query']!r} reason={row['reason']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
