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
    "agentur",
    "agenzia",
    "agencia",
    "telegraph",
    "telegraphen",
    "telegraphique",
    "télégraphique",
    "presse",
    "press",
    "nachrichtenagentur",
    "radio",
    "rundfunk",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_metadata(paths: list[Path]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.is_file():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "")
            if label:
                metadata[label] = row
    return metadata


def family_for_label(label: str) -> str:
    if label.startswith("org.ent.pressagency."):
        return "pressagency"
    if label.startswith("org.ent.radiostation."):
        return "radiostation"
    if label.startswith("org.ent.newspaper."):
        return "newspaper"
    return "other"


def normalize_surface(surface: str) -> str:
    return re.sub(r"\s+", " ", surface.strip()).casefold()


def surface_tokens(surface: str) -> list[str]:
    return [token.casefold() for token in re.findall(r"[\wÀ-ÿ]+", surface, flags=re.UNICODE)]


def generic_terms(surface: str) -> list[str]:
    return sorted({token for token in surface_tokens(surface) if token in GENERIC_TERMS})


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language") or row.get("search_language") or "unknown")


def entity_surface(row: dict[str, Any], entity: dict[str, Any]) -> str:
    surface = str(entity.get("surface") or "")
    if surface:
        return surface
    text = str(row.get("text") or "")
    start = entity.get("start")
    stop = entity.get("stop")
    if start is not None and stop is not None:
        return text[int(start) : int(stop)]
    return ""


def build_profiles(args: argparse.Namespace) -> dict[str, Any]:
    metadata = load_metadata(args.label_metadata)
    by_label_surface: dict[str, Counter[str]] = defaultdict(Counter)
    by_label_surface_language: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    display_by_key: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    by_label_language: dict[str, Counter[str]] = defaultdict(Counter)
    by_label_source: dict[str, Counter[str]] = defaultdict(Counter)
    source_rows: dict[str, int] = {}
    source_entities: dict[str, int] = {}

    for raw_source in args.input_jsonl:
        source_name, path_text = raw_source.split("=", 1) if "=" in raw_source else (Path(raw_source).stem, raw_source)
        path = Path(path_text)
        rows = load_jsonl(path)
        source_rows[source_name] = len(rows)
        source_entities[source_name] = 0
        for row in rows:
            language = row_language(row)
            for entity in row.get("entities") or []:
                if not isinstance(entity, dict):
                    continue
                label = str(entity.get("label") or "")
                if not label.startswith("org.ent."):
                    continue
                surface = entity_surface(row, entity)
                if not surface:
                    continue
                key = normalize_surface(surface)
                by_label_surface[label][key] += 1
                by_label_surface_language[(label, language)][key] += 1
                display_by_key[(label, key)][surface] += 1
                by_label_language[label][language] += 1
                by_label_source[label][source_name] += 1
                source_entities[source_name] += 1

    rows_out: list[dict[str, Any]] = []
    profiles = []
    for label in sorted(by_label_surface):
        total = sum(by_label_surface[label].values())
        top_surfaces = []
        for key, count in by_label_surface[label].most_common(args.top_n):
            display = display_by_key[(label, key)].most_common(1)[0][0]
            terms = generic_terms(display)
            languages = {
                language: by_label_surface_language[(label, language)][key]
                for language in sorted(by_label_language[label])
                if by_label_surface_language[(label, language)][key]
            }
            item = {
                "surface": display,
                "normalized_surface": key,
                "count": count,
                "share": round(count / total, 4) if total else 0.0,
                "languages": languages,
                "generic_terms": terms,
            }
            top_surfaces.append(item)
            rows_out.append(
                {
                    "label": label,
                    "family": family_for_label(label),
                    "canonical_id": metadata.get(label, {}).get("canonical_id") or label.rsplit(".", 1)[-1],
                    "display_name": metadata.get(label, {}).get("display_name") or label,
                    "surface": display,
                    "normalized_surface": key,
                    "count": count,
                    "share": f"{item['share']:.4f}",
                    "languages": ", ".join(f"{language}:{value}" for language, value in languages.items()),
                    "generic_terms": ", ".join(terms),
                }
            )
        profiles.append(
            {
                "label": label,
                "family": family_for_label(label),
                "canonical_id": metadata.get(label, {}).get("canonical_id") or label.rsplit(".", 1)[-1],
                "display_name": metadata.get(label, {}).get("display_name") or label,
                "total": total,
                "languages": dict(sorted(by_label_language[label].items())),
                "sources": dict(sorted(by_label_source[label].items())),
                "top_surfaces": top_surfaces,
            }
        )

    return {
        "inputs": args.input_jsonl,
        "source_rows": source_rows,
        "source_entities": source_entities,
        "top_n": args.top_n,
        "profiles": profiles,
        "surface_rows": rows_out,
    }


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "family",
        "label",
        "canonical_id",
        "display_name",
        "surface",
        "normalized_surface",
        "count",
        "share",
        "languages",
        "generic_terms",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path: Path, profiles: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Entity Mention Profiles", ""]
    for profile in profiles:
        lines.append(f"## {profile['display_name']}")
        lines.append("")
        lines.append(f"- Label: `{profile['label']}`")
        lines.append(f"- Total mentions: {profile['total']}")
        if profile["languages"]:
            lines.append("- Languages: " + ", ".join(f"{key}={value}" for key, value in profile["languages"].items()))
        lines.append("")
        lines.append("| Surface | Count | Share | Languages | Generic terms |")
        lines.append("|---|---:|---:|---|---|")
        for surface in profile["top_surfaces"]:
            languages = ", ".join(f"{key}:{value}" for key, value in surface["languages"].items())
            terms = ", ".join(surface["generic_terms"])
            lines.append(f"| {surface['surface']} | {surface['count']} | {surface['share']:.2%} | {languages} | {terms} |")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate empirical mention-surface profiles by entity label.")
    parser.add_argument("--input-jsonl", action="append", default=[], help="Input JSONL, optionally named as source=path.")
    parser.add_argument("--label-metadata", type=Path, action="append", default=[])
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--tsv-output", type=Path)
    parser.add_argument("--md-output", type=Path)
    return parser.parse_args(argv)


def fill_defaults(args: argparse.Namespace) -> argparse.Namespace:
    if not args.label_metadata:
        args.label_metadata = [Path("resources/newsagency_seeds.json"), Path("resources/radiostation_seeds.json")]
    return args


def main(argv: list[str] | None = None) -> int:
    args = fill_defaults(parse_args(argv))
    report = build_profiles(args)
    summary = {
        "inputs": report["inputs"],
        "labels": len(report["profiles"]),
        "source_rows": report["source_rows"],
        "source_entities": report["source_entities"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.tsv_output:
        write_tsv(args.tsv_output, report["surface_rows"])
    if args.md_output:
        write_markdown(args.md_output, report["profiles"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
