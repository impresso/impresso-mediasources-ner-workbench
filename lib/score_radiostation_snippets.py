from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .score_newsagency_snippets import (
    all_generic_alias_spans,
    attach_surfaces,
    device_for,
    import_runtime,
    is_unclosed_dotted_acronym,
    labels_to_spans,
    load_generic_label_metadata,
    merge_adjacent_same_label_spans,
    normalize_dotted_acronym_spans,
    resolve_model_ref,
    score_tokens,
    suppress_overlapping_spans,
    validate_model_inference_metadata,
)
from .snippet_data import candidate_id, candidate_tokens, load_jsonl, write_jsonl
from .temporal_verification import verify_entity_start_year


PATTERN_MATCH_CONFIDENCE = 0.51


def normalize_station_id(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def load_station_metadata(path: Path) -> dict[str, dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        station_id = normalize_station_id(row.get("canonical_id"))
        label = str(row.get("label", ""))
        if station_id and label.startswith("org.ent.radiostation."):
            metadata[station_id] = row
    return metadata


def load_pressagency_metadata(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = str(row.get("label", ""))
        canonical_id = str(row.get("canonical_id") or label.rsplit(".", 1)[-1])
        if canonical_id and label.startswith("org.ent.pressagency."):
            metadata[canonical_id] = row
    return metadata


def seed_aliases(seed: dict[str, Any]) -> list[str]:
    aliases = []
    for alias in seed.get("aliases") or []:
        if isinstance(alias, str) and alias.strip():
            aliases.append(alias.strip())
    aliases_by_language = seed.get("aliases_by_language") or {}
    if isinstance(aliases_by_language, dict):
        for values in aliases_by_language.values():
            for alias in values or []:
                if isinstance(alias, str) and alias.strip():
                    aliases.append(alias.strip())
    display = seed.get("display_name")
    if isinstance(display, str) and display.strip():
        aliases.append(display.strip())
    return unique_strings(aliases)


def build_alias_index(metadata: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for seed in metadata.values():
        for alias in seed_aliases(seed):
            key = compact(alias)
            if key and key not in index:
                index[key] = seed
    return index


def row_station_id(row: dict[str, Any]) -> str:
    station = normalize_station_id(row.get("station") or row.get("agency"))
    if station:
        return station
    label = str(row.get("candidate_label") or row.get("label") or "")
    if label.startswith("org.ent.radiostation."):
        return normalize_station_id(label.rsplit(".", 1)[-1])
    return ""


def unique_strings(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


def non_generic_radio_label(row: dict[str, Any]) -> str:
    label = str(row.get("candidate_label") or row.get("label") or "")
    if label.startswith("org.ent.radiostation.") and label != "org.ent.radiostation":
        return label
    return ""


def aliases_for_row(
    row: dict[str, Any],
    metadata: dict[str, dict[str, Any]],
    alias_index: dict[str, dict[str, Any]],
) -> tuple[str, list[str]]:
    station_id = row_station_id(row)
    aliases = []
    query = str(row.get("query") or "").strip()
    if query:
        aliases.append(query)
    seed = metadata.get(station_id) or alias_index.get(compact(query)) or {}
    aliases.extend(seed_aliases(seed))
    label = str(seed.get("label") or non_generic_radio_label(row))
    return label, unique_strings(aliases)


def token_window_surface(tokens: list[str], start: int, stop: int) -> str:
    return " ".join(tokens[start:stop])


def compact(value: str) -> str:
    return re.sub(r"\W+", "", value, flags=re.UNICODE).casefold()


def has_word_char(value: str) -> bool:
    return bool(re.search(r"\w", value, flags=re.UNICODE))


def alias_matches_hyphenated_suffix(tokens: list[str], start: int, stop: int, alias: str) -> bool:
    alias_words = re.findall(r"\w+", alias, flags=re.UNICODE)
    if not alias_words:
        return False
    if stop - start == len(alias_words) + 2 and tokens[stop - 2] == "-":
        return all(compact(tokens[start + offset]) == compact(word) for offset, word in enumerate(alias_words))
    if stop - start != len(alias_words):
        return False
    for offset, alias_word in enumerate(alias_words[:-1]):
        if compact(tokens[start + offset]) != compact(alias_word):
            return False
    final_token = tokens[stop - 1]
    if "-" not in final_token:
        return False
    prefix = final_token.split("-", 1)[0]
    return compact(prefix) == compact(alias_words[-1])


def find_alias_spans(tokens: list[str], aliases: list[str], label: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    seen = set()
    alias_forms = [
        (alias, compact(alias), len(re.findall(r"\w+|[^\w\s]", alias, flags=re.UNICODE)))
        for alias in aliases
        if compact(alias)
    ]
    max_len = max((len(re.findall(r"\w+|[^\w\s]", alias, flags=re.UNICODE)) for alias in aliases), default=1) + 2
    for start in range(len(tokens)):
        for stop in range(start + 1, min(len(tokens), start + max_len) + 1):
            if not has_word_char(tokens[start]):
                continue
            surface = token_window_surface(tokens, start, stop)
            surface_compact = compact(surface)
            for alias, alias_compact, alias_token_len in alias_forms:
                alias_tail = alias.rstrip()[-1:]
                if has_word_char(tokens[stop - 1]) and not has_word_char(alias_tail) and stop < len(tokens) and tokens[stop] == alias_tail:
                    continue
                if not has_word_char(tokens[stop - 1]) and has_word_char(alias.rstrip()[-1:]):
                    continue
                if not has_word_char(tokens[stop - 1]) and not has_word_char(alias_tail) and tokens[stop - 1] != alias_tail:
                    continue
                if (
                    not has_word_char(tokens[stop - 1])
                    and not has_word_char(alias.rstrip()[-1:])
                    and re.search(r"\W", alias.rstrip()[:-1], flags=re.UNICODE)
                    and not re.search(r"\W", token_window_surface(tokens, start, stop - 1), flags=re.UNICODE)
                ):
                    continue
                matcher = "alias_compact"
                if surface_compact != alias_compact:
                    if not alias_matches_hyphenated_suffix(tokens, start, stop, alias):
                        continue
                    matcher = "alias_hyphenated_suffix"
                else:
                    if len(re.findall(r"\w+", surface, flags=re.UNICODE)) != len(
                        re.findall(r"\w+", alias, flags=re.UNICODE)
                    ):
                        continue
                    if any(token in {"(", ")", "[", "]", "{", "}"} for token in tokens[start:stop]):
                        continue
                    matcher = "alias_compact"
                actual_stop = stop
                if alias.rstrip().endswith(".") and stop < len(tokens) and tokens[stop] == "." and is_unclosed_dotted_acronym(tokens, start, stop):
                    actual_stop = stop + 1
                key = (start, actual_stop, label)
                if key in seen:
                    continue
                seen.add(key)
                spans.append(
                    {
                        "token_start": start,
                        "token_stop": actual_stop,
                        "label": label,
                        "surface": token_window_surface(tokens, start, actual_stop),
                        "confidence": PATTERN_MATCH_CONFIDENCE,
                        "margin": PATTERN_MATCH_CONFIDENCE,
                        "matcher": matcher,
                        "alias": alias,
                    }
                )
    return suppress_one_letter_alias_extensions(spans, tokens)


def suppress_one_letter_alias_extensions(spans: list[dict[str, Any]], tokens: list[str]) -> list[dict[str, Any]]:
    shorter_keys = {
        (int(span["token_start"]), int(span["token_stop"]), str(span["label"]))
        for span in spans
    }
    out = []
    for span in spans:
        start = int(span["token_start"])
        stop = int(span["token_stop"])
        label = str(span["label"])
        if (
            stop - start > 1
            and (start, stop - 1, label) in shorter_keys
            and tokens[stop - 1].isalpha()
            and len(tokens[stop - 1]) == 1
        ):
            continue
        out.append(span)
    return out


def high_precision_press_aliases(seed: dict[str, Any]) -> list[str]:
    aliases = []
    for alias in seed_aliases(seed):
        compact_alias = compact(alias)
        # Avoid noisy global matches for very short acronyms such as AP or ATS.
        if len(compact_alias) < 4 and not any(char in alias for char in ".-/"):
            continue
        aliases.append(alias)
    return aliases


def find_all_seed_alias_spans(tokens: list[str], metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for seed in metadata.values():
        label = str(seed.get("label") or "")
        if not label:
            continue
        spans.extend(find_alias_spans(tokens, seed_aliases(seed), label))
    return spans


def find_all_press_alias_spans(tokens: list[str], metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for seed in metadata.values():
        label = str(seed.get("label") or "")
        if not label:
            continue
        spans.extend(find_alias_spans(tokens, high_precision_press_aliases(seed), label))
        spans.extend(find_contextual_source_formula_spans(tokens, seed, label))
    return spans


def find_contextual_source_formula_spans(tokens: list[str], seed: dict[str, Any], label: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for item in seed.get("contextual_aliases") or []:
        if not isinstance(item, dict):
            continue
        use = str(item.get("use") or "")
        alias = str(item.get("alias") or "").strip()
        if not alias:
            continue
        for span in find_alias_spans(tokens, [alias], label):
            start = int(span["token_start"])
            stop = int(span["token_stop"])
            if use == "dispatch_source_formula":
                closes_formula = stop < len(tokens) and tokens[stop] == ")"
                closes_after_period = stop + 1 < len(tokens) and tokens[stop] == "." and tokens[stop + 1] == ")"
                matches_context = start > 0 and tokens[start - 1] == "(" and (closes_formula or closes_after_period)
                matcher = "contextual_dispatch_source_formula"
            elif use == "reporting_verb_context":
                reporting_words = {
                    "added", "said", "reported", "stated", "announced",
                    "ajoute", "ajouté", "annonce", "annoncé", "déclare", "déclaré", "indique", "indiqué", "rapporte", "rapporté", "révèle", "révélé",
                    "berichtete", "berichtet", "erklärte", "erklart", "meldete", "meldet",
                }
                context = {token.casefold() for token in tokens[max(0, start - 3) : min(len(tokens), stop + 3)]}
                matches_context = bool(context & reporting_words)
                matcher = "contextual_reporting_verb"
            else:
                continue
            if matches_context:
                contextual = dict(span)
                contextual["matcher"] = matcher
                spans.append(contextual)
    return spans


def attach_offsets(spans: list[dict[str, Any]], starts: list[int], stops: list[int], text: str) -> list[dict[str, Any]]:
    out = []
    for span in spans:
        start = int(span["token_start"])
        stop = int(span["token_stop"])
        if start < 0 or stop <= start or stop > len(starts):
            continue
        item = dict(span)
        item["start"] = starts[start]
        item["stop"] = stops[stop - 1]
        item["surface"] = text[item["start"] : item["stop"]]
        out.append(item)
    return out


def dedupe_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for span in spans:
        key = (int(span["token_start"]), int(span["token_stop"]), str(span["label"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(span)
    return out


def suppress_model_spans_covered_by_aliases(
    model_spans: list[dict[str, Any]], alias_spans: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    alias_boundaries = {
        (int(span["token_start"]), int(span["token_stop"]))
        for span in alias_spans
    }
    return [
        span
        for span in model_spans
        if (int(span["token_start"]), int(span["token_stop"])) not in alias_boundaries
    ]


def load_model_runtime(args: argparse.Namespace) -> tuple[Any, Any, Any, Any, Any] | None:
    model_name = str(getattr(args, "model", "") or "")
    if not model_name:
        return None
    torch, model_cls, tokenizer_cls = import_runtime()
    model_ref = resolve_model_ref(model_name)
    device = device_for(str(getattr(args, "device", "auto")), torch)
    tokenizer = tokenizer_cls.from_pretrained(model_ref)
    model = model_cls.from_pretrained(model_ref).to(device)
    validate_model_inference_metadata(model.config, model_name)
    model.eval()
    return torch, tokenizer, model, device, model_name


def score_rows(args: argparse.Namespace) -> dict[str, Any]:
    metadata = load_station_metadata(Path(args.radiostations))
    press_metadata = load_pressagency_metadata(Path(getattr(args, "newsagencies", "resources/newsagency_seeds.json")))
    newspapers_path = Path(getattr(args, "newspapers", "resources/newspaper_seeds.json"))
    newspaper_metadata = load_generic_label_metadata(newspapers_path, expected_prefix="org.ent.newspaper.")
    label_metadata = {
        str(seed.get("label")): seed
        for seed in [*metadata.values(), *press_metadata.values()]
        if str(seed.get("label") or "").startswith("org.ent.")
    }
    alias_index = build_alias_index(metadata)
    model_runtime = load_model_runtime(args)
    rows = []
    counts = {"needs_review": 0, "no_alias_match": 0, "model_span": 0, "unresolved_label": 0}
    for index, row in enumerate(load_jsonl(Path(args.input)), start=1):
        text, tokens, starts, stops = candidate_tokens(row)
        label, aliases = aliases_for_row(row, metadata, alias_index)
        candidate_alias_spans = find_alias_spans(tokens, aliases, label) if label else []
        all_alias_spans = find_all_seed_alias_spans(tokens, metadata)
        press_alias_spans = find_all_press_alias_spans(tokens, press_metadata)
        newspaper_alias_spans = all_generic_alias_spans(tokens, newspaper_metadata)
        alias_spans = attach_offsets(
            dedupe_spans(candidate_alias_spans + all_alias_spans + press_alias_spans + newspaper_alias_spans),
            starts,
            stops,
            text,
        )
        model_spans: list[dict[str, Any]] = []
        if model_runtime is not None:
            torch, tokenizer, model, device, _model_name = model_runtime
            labels, confidences, margins = score_tokens(
                tokens,
                tokenizer,
                model,
                torch,
                device,
                int(getattr(args, "max_sequence_len", 512)),
                float(getattr(args, "suggest_non_o_min_confidence", 0.33)),
            )
            model_spans = normalize_dotted_acronym_spans(
                attach_surfaces(labels_to_spans(labels, confidences, margins), tokens, starts, stops, text),
                tokens,
                starts,
                stops,
                text,
            )
            model_spans = suppress_model_spans_covered_by_aliases(model_spans, alias_spans)
        spans = merge_adjacent_same_label_spans(
            suppress_overlapping_spans(dedupe_spans(alias_spans + model_spans)), text
        )
        out = dict(row)
        out["id"] = candidate_id(row, index)
        out["candidate_label"] = label or None
        out["entity_family"] = "radiostation"
        out["text"] = text
        out["tokens"] = tokens
        out["token_start_offsets"] = starts
        out["token_end_offsets"] = stops
        out["model"] = {
            "repo_id": str(getattr(args, "model", "") or "alias-matcher"),
            "suggest_non_o_min_confidence": float(getattr(args, "suggest_non_o_min_confidence", 0.33)),
            "scorers": ["radiostation_alias_matcher", "pressagency_alias_matcher"]
            + (["newspaper_alias_matcher"] if newspapers_path.is_file() else [])
            + (["token_classifier"] if model_runtime is not None else []),
            "predicted_spans": spans,
        }
        temporal_verification = verify_entity_start_year(row=row, label=label or None, label_metadata=label_metadata)
        out["temporal_verification"] = temporal_verification
        reasons = []
        if not label:
            reasons.append("unresolved_radiostation_label")
        if not alias_spans:
            reasons.append("no_alias_span_match")
        if model_runtime is not None and model_spans:
            reasons.append("model_predicted_mediaagency_span")
        if temporal_verification["status"] == "suspicious_before_start":
            reasons.append("suspicious_before_entity_start")
        out["curation"] = {
            "status": "needs_review",
            "label": out["candidate_label"],
            "reasons": reasons,
            "reviewer": None,
            "reviewed_at": None,
            "notes": None,
        }
        counts["needs_review"] += 1
        if not alias_spans:
            counts["no_alias_match"] += 1
        if model_spans:
            counts["model_span"] += 1
        if not label:
            counts["unresolved_label"] += 1
        rows.append(out)
    write_jsonl(Path(args.output), rows)
    return {"rows": len(rows), **counts, "output": args.output}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score radio-station snippets with deterministic seed alias matching.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--radiostations", default="resources/radiostation_seeds.json")
    parser.add_argument("--newsagencies", default="resources/newsagency_seeds.json")
    parser.add_argument("--newspapers", default="resources/newspaper_seeds.json")
    parser.add_argument("--model", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-sequence-len", type=int, default=512)
    parser.add_argument("--suggest-non-o-min-confidence", type=float, default=0.33)
    parser.add_argument("--auto-accept-min-confidence", type=float, default=0.99)
    parser.add_argument("--auto-accept-min-margin", type=float, default=0.30)
    parser.add_argument("--auto-accept-multiple-min-confidence", type=float, default=0.99)
    parser.add_argument("--auto-accept", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(json.dumps(score_rows(args), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
