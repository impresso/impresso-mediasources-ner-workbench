from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("document_id") or row.get("id") or "")


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
    token_start = entity.get("token_start")
    token_stop = entity.get("token_stop")
    tokens = row.get("tokens") or []
    if token_start is not None and token_stop is not None:
        return " ".join(str(token) for token in tokens[int(token_start) : int(token_stop)])
    return ""


def normalize_surface(surface: str) -> str:
    return re.sub(r"\s+", " ", surface.strip()).casefold()


def display_form(forms: Counter[str]) -> str:
    return forms.most_common(1)[0][0] if forms else ""


def build_frequency_report(input_paths: list[Path], *, label: str, include_examples: int = 0) -> dict[str, Any]:
    if not label:
        raise ValueError("label is required")
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    forms: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    examples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    source_rows: dict[str, int] = {}
    source_entities: dict[str, int] = {}
    total = 0

    for path in input_paths:
        source = str(path)
        rows = load_jsonl(path)
        source_rows[source] = len(rows)
        source_entities[source] = 0
        for row in rows:
            language = row_language(row)
            for entity in row.get("entities") or []:
                if not isinstance(entity, dict) or entity.get("label") != label:
                    continue
                surface = entity_surface(row, entity)
                if not surface:
                    continue
                normalized = normalize_surface(surface)
                counts[language][normalized] += 1
                forms[(language, normalized)][surface] += 1
                source_entities[source] += 1
                total += 1
                if include_examples and len(examples[(language, normalized)]) < include_examples:
                    examples[(language, normalized)].append(
                        {
                            "document_id": row_id(row),
                            "surface": surface,
                            "source": source,
                        }
                    )

    languages: dict[str, Any] = {}
    for language in sorted(counts):
        surfaces = {}
        language_total = sum(counts[language].values())
        for normalized, count in counts[language].most_common():
            item = {
                "count": count,
                "forms": dict(forms[(language, normalized)].most_common()),
                "display": display_form(forms[(language, normalized)]),
            }
            if include_examples:
                item["examples"] = examples[(language, normalized)]
            surfaces[normalized] = item
        languages[language] = {
            "total": language_total,
            "surfaces": surfaces,
        }

    return {
        "label": label,
        "total": total,
        "inputs": [str(path) for path in input_paths],
        "source_rows": source_rows,
        "source_entities": source_entities,
        "languages": languages,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write case-insensitive mention-surface frequencies for one entity label.")
    parser.add_argument("--label", required=True)
    parser.add_argument("--input-jsonl", action="append", type=Path, default=[])
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--include-examples", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_frequency_report(args.input_jsonl, label=args.label, include_examples=args.include_examples)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
