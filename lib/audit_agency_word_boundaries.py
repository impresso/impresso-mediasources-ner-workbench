from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from lib.audit_existing_spans import write_json, write_jsonl
from lib.span_patch_review import stable_review_id


AGENCY_WORDS = {
    "agence",
    "agences",
    "agency",
    "agentur",
    "agenzia",
    "nachrichtenbureau",
    "gence",
    "lagence",
    "nachrichtenagentur",
    "nachrichten-agentur",
    "presseagentur",
    "presse-agentur",
}


def normalize(value: str) -> str:
    value = value.casefold()
    value = value.replace("’", "'")
    value = re.sub(r"[^0-9a-zà-öø-ÿ]+", " ", value)
    return " ".join(value.split())


KEEP_FULL_SURFACES = {
    normalize("Agence France-Presse"),
    normalize("Agence France Presse"),
    normalize("Agence Radio"),
    normalize("Agence Télégraphique Radio"),
    normalize("Agence Téléradio"),
    normalize("Agence Chine nouvelle"),
    normalize("Agence Chine Nouvelle"),
    normalize("Agence télégraphique suisse"),
    normalize("Agence Telegraphique Suisse"),
    normalize("Agence Kampuchea Presse"),
    normalize("Agence Kampuchea Press"),
    normalize("Agence télégraphique albanaise"),
    normalize("Agence de presse internationale catholique"),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_decisions(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def tsv_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_preview_tsv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(tsv_cell(row.get(column, "")) for column in columns) + "\n")


def nonempty_file(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def metadata_aliases(row: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for key in ("display_name", "aliases", "search_aliases"):
        value = row.get(key)
        if isinstance(value, str):
            aliases.append(value)
        elif isinstance(value, list):
            aliases.extend(str(item) for item in value if item)
    aliases_by_language = row.get("aliases_by_language")
    if isinstance(aliases_by_language, dict):
        for values in aliases_by_language.values():
            if isinstance(values, list):
                aliases.extend(str(item) for item in values if item)
    contextual_aliases = row.get("contextual_aliases")
    if isinstance(contextual_aliases, list):
        for item in contextual_aliases:
            if isinstance(item, dict) and item.get("alias"):
                aliases.append(str(item["alias"]))
    return aliases


def load_metadata(path: Path) -> dict[str, dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["label"]): row for row in rows if isinstance(row, dict) and row.get("label")}


def strip_leading_agency_words(alias: str) -> str:
    parts = normalize(alias).split()
    while parts and parts[0] in {"l", "la", "le", "les", "a"}:
        parts = parts[1:]
    while parts and parts[0] in AGENCY_WORDS:
        parts = parts[1:]
    while parts and parts[0] in {"de", "du", "des", "d", "of", "the", "telegraphique", "semi", "officielle", "semi officielle"}:
        parts = parts[1:]
    return " ".join(parts)


def core_aliases(metadata: dict[str, dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
    out: dict[str, dict[str, set[str]]] = {}
    for label, row in metadata.items():
        policy = row.get("agency_word_boundary_policy") if isinstance(row.get("agency_word_boundary_policy"), dict) else {}
        if not policy.get("migrate_strip_agency_words"):
            continue
        strip_short_name = policy.get("policy") == "strip_short_name"
        values: set[str] = set()
        direct_values: set[str] = set()
        for alias in metadata_aliases(row):
            norm = normalize(alias)
            stripped = strip_leading_agency_words(alias)
            if norm:
                values.add(norm)
                if not strip_short_name or norm == stripped:
                    direct_values.add(norm)
            if stripped:
                values.add(stripped)
        out[label] = {"any": values, "direct": direct_values}
    return out


def token_char_span(row: dict[str, Any], start: int, stop: int) -> tuple[int, int]:
    starts = [int(value) for value in row.get("token_start_offsets") or []]
    stops = [int(value) for value in row.get("token_end_offsets") or []]
    return starts[start], stops[stop - 1]


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("document_id") or row.get("id") or "")


def proposed_suffix(row: dict[str, Any], entity: dict[str, Any], aliases: dict[str, set[str]]) -> tuple[int, int] | None:
    tokens = [str(token) for token in row.get("tokens") or []]
    start = int(entity["token_start"])
    stop = int(entity["token_stop"])
    while stop > start and not any(char.isalnum() for char in tokens[stop - 1]):
        stop -= 1
    if stop - start < 2:
        return None
    if normalize(" ".join(tokens[start:stop])) in KEEP_FULL_SURFACES:
        return None
    first_norm = normalize(tokens[start])
    prefix_norm = normalize(" ".join(tokens[start : min(stop, start + 4)]))
    has_agency_word = first_norm in AGENCY_WORDS or any(normalize(token) in AGENCY_WORDS for token in tokens[start : min(stop, start + 4)])
    has_noisy_agency_prefix = any(word in prefix_norm for word in ("agence", "gence", "agentur", "agenzia", "lagence", "ng nzia"))
    if not has_agency_word and not has_noisy_agency_prefix:
        return None
    direct_aliases = aliases["direct"]
    any_aliases = aliases["any"]
    for length in range(stop - start, 0, -1):
        for suffix_start in range(start, stop - length + 1):
            suffix_stop = suffix_start + length
            if not has_core_name_token(tokens[suffix_start:suffix_stop]):
                continue
            surface = " ".join(tokens[suffix_start:suffix_stop])
            if normalize(surface) in direct_aliases:
                return trim_edge_punctuation(tokens, suffix_start, suffix_stop)
    for suffix_start in range(stop - 1, start, -1):
        if not has_core_name_token(tokens[suffix_start:stop]):
            continue
        surface = " ".join(tokens[suffix_start:stop])
        if normalize(surface) in any_aliases:
            return trim_edge_punctuation(tokens, suffix_start, stop)
    return None


def trim_edge_punctuation(tokens: list[str], start: int, stop: int) -> tuple[int, int]:
    while start < stop and not any(char.isalnum() for char in tokens[start]):
        start += 1
    while stop > start and not any(char.isalnum() for char in tokens[stop - 1]):
        stop -= 1
    return start, stop


def has_core_name_token(tokens: list[str]) -> bool:
    for token in tokens:
        letters = [char for char in token if char.isalpha()]
        if len(letters) >= 2 and all(char.isupper() for char in letters):
            return True
        if len(letters) >= 3 and letters[0].isupper() and any(char.islower() for char in letters[1:]):
            return True
    return False


def make_candidate(row: dict[str, Any], entity: dict[str, Any], audit_id: str) -> dict[str, Any]:
    old_start = int(entity["start"])
    old_stop = int(entity["stop"])
    span = {
        "label": entity["label"],
        "start": old_start,
        "stop": old_stop,
        "surface": entity.get("surface") or str(row.get("text") or "")[old_start:old_stop],
        "token_start": entity.get("token_start"),
        "token_stop": entity.get("token_stop"),
    }
    return {
        "audit_mode": "agency-word-boundary",
        "date": row.get("date", ""),
        "document_id": row_id(row),
        "language": row.get("language", ""),
        "newspaper": row.get("newspaper", ""),
        "candidate_spans": [span],
        "target_label": entity["label"],
        "text": row.get("text", ""),
        "token_end_offsets": row.get("token_end_offsets", []),
        "token_start_offsets": row.get("token_start_offsets", []),
        "tokens": row.get("tokens", []),
    }


def make_decision(candidate: dict[str, Any], entity: dict[str, Any], new_span: dict[str, Any], audit_id: str, reviewer: str, notes: str) -> dict[str, Any]:
    review_id = stable_review_id(audit_id, str(candidate["document_id"]), int(entity["start"]), int(entity["stop"]), str(entity["label"]))
    reviewed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "audit_id": audit_id,
        "audit_marker": f"{reviewer}:{reviewed_at[:10]}:verified",
        "audit_status": "verified",
        "choice": "modify",
        "correct_label": entity["label"],
        "document_id": candidate["document_id"],
        "notes": notes,
        "review_id": review_id,
        "reviewed_at": reviewed_at,
        "reviewer": reviewer,
        "source": {
            "label": entity["label"],
            "start": int(entity["start"]),
            "stop": int(entity["stop"]),
            "surface": entity.get("surface", ""),
            "token_start": entity.get("token_start"),
            "token_stop": entity.get("token_stop"),
        },
        "span": new_span,
        "status": "verified",
        "target_label": entity["label"],
    }


def build_boundary_migration(
    *,
    input_jsonl: Path,
    metadata_path: Path,
    audit_id: str,
    split: str,
    reviewer: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows = load_jsonl(input_jsonl)
    metadata = load_metadata(metadata_path)
    aliases_by_label = core_aliases(metadata)
    candidates: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    tsv_rows: list[dict[str, Any]] = []
    by_label: dict[str, int] = {}
    by_language: dict[str, int] = {}
    changes_preview: list[dict[str, Any]] = []

    for row in rows:
        for entity in row.get("entities") or []:
            if not isinstance(entity, dict):
                continue
            label = str(entity.get("label") or "")
            if ".pressagency." not in label or label not in aliases_by_label:
                continue
            proposal = proposed_suffix(row, entity, aliases_by_label[label])
            if proposal is None:
                continue
            new_token_start, new_token_stop = proposal
            new_start, new_stop = token_char_span(row, new_token_start, new_token_stop)
            if new_start == int(entity["start"]) and new_stop == int(entity["stop"]):
                continue
            text = str(row.get("text") or "")
            candidate = make_candidate(row, entity, audit_id)
            new_span = {
                "label": label,
                "start": new_start,
                "stop": new_stop,
                "surface": text[new_start:new_stop],
                "token_start": new_token_start,
                "token_stop": new_token_stop,
            }
            candidates.append(candidate)
            decisions.append(make_decision(candidate, candidate["candidate_spans"][0], new_span, audit_id, reviewer, "Automatic agency-word boundary migration."))
            preview = {
                "audit_id": audit_id,
                "date": row.get("date", ""),
                "document_id": row_id(row),
                "language": row.get("language", ""),
                "label": label,
                "new_span": new_span["surface"],
                "new_token_start": new_token_start,
                "new_token_stop": new_token_stop,
                "new_start": new_start,
                "new_stop": new_stop,
                "old_span": candidate["candidate_spans"][0]["surface"],
                "old_token_start": entity.get("token_start"),
                "old_token_stop": entity.get("token_stop"),
                "old_start": entity.get("start"),
                "old_stop": entity.get("stop"),
                "split": split,
            }
            changes_preview.append(preview)
            tsv_rows.append(preview)
            by_label[label] = by_label.get(label, 0) + 1
            language = str(row.get("language") or "")
            by_language[language] = by_language.get(language, 0) + 1

    candidates.sort(key=lambda item: (str(item["document_id"]), int(item["candidate_spans"][0]["start"]), str(item["target_label"])))
    decisions.sort(key=lambda item: (str(item["document_id"]), int(item["source"]["start"]), str(item["target_label"])))
    tsv_rows.sort(key=lambda item: (str(item["document_id"]), int(item["old_start"]), str(item["label"])))
    changes_preview.sort(key=lambda item: (str(item["document_id"]), int(item["old_start"]), str(item["label"])))
    summary = {
        "audit_id": audit_id,
        "audit_mode": "agency-word-boundary",
        "split": split,
        "input_jsonl": str(input_jsonl),
        "candidate_documents": len({row["document_id"] for row in tsv_rows}),
        "candidate_spans": len(tsv_rows),
        "candidate_spans_by_label": dict(sorted(by_label.items())),
        "candidate_spans_by_language": dict(sorted(by_language.items())),
        "decisions_written": len(decisions),
    }
    return candidates, decisions, tsv_rows, changes_preview, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build accepted span patches to migrate generic agency-word boundaries to core names.")
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--label-metadata", required=True)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--candidates-jsonl", required=True)
    parser.add_argument("--decisions-jsonl", required=True)
    parser.add_argument("--changes-jsonl", required=True)
    parser.add_argument("--changes-tsv", required=True)
    parser.add_argument("--summary-json", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates, decisions, tsv_rows, changes_preview, summary = build_boundary_migration(
        input_jsonl=Path(args.input_jsonl),
        metadata_path=Path(args.label_metadata),
        audit_id=args.audit_id,
        split=args.split,
        reviewer=args.reviewer,
    )
    preserve_applied_files = not candidates and (nonempty_file(Path(args.candidates_jsonl)) or nonempty_file(Path(args.decisions_jsonl)))
    if preserve_applied_files:
        summary["preserved_existing_candidate_or_decision_files"] = True
    else:
        write_jsonl(Path(args.candidates_jsonl), candidates)
        write_decisions(Path(args.decisions_jsonl), decisions)
    write_jsonl(Path(args.changes_jsonl), changes_preview)
    write_preview_tsv(
        Path(args.changes_tsv),
        tsv_rows,
        ["split", "document_id", "language", "date", "label", "old_span", "new_span", "old_token_start", "old_token_stop", "new_token_start", "new_token_stop"],
    )
    write_json(Path(args.summary_json), summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
