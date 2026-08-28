from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .env import load_dotenv_if_available
from .snippet_data import candidate_id, candidate_tokens, load_jsonl, write_jsonl
from .temporal_verification import verify_entity_start_year

try:
    from mediaagency_modernbert.decoding import (
        DECODER_FIRST_SUBTOKEN,
        DECODER_FIRST_SUBTOKEN_VITERBI,
        compile_bio_schema,
        decode_document,
        semantic_label_margin,
        semantic_label_probability,
    )
except ImportError:
    DECODER_FIRST_SUBTOKEN = "first_subtoken"
    DECODER_FIRST_SUBTOKEN_VITERBI = "first_subtoken_viterbi"
    compile_bio_schema = None
    decode_document = None
    semantic_label_probability = None
    semantic_label_margin = None

DEFAULT_SEARCH_SNIPPETS = Path("data/candidates/newsagency_search_snippets.jsonl")
DEFAULT_LEGACY_SNIPPETS = Path("data/candidates/newsagency_legacy_snippets.jsonl")


def resolve_model_ref(value: str) -> str:
    return value[len("hf://") :] if value.startswith("hf://") else value


def candidate_label(row: dict[str, Any]) -> str:
    for field in ("candidate_label", "label", "target_label"):
        value = row.get(field)
        if isinstance(value, str) and value.startswith("org.ent.pressagency."):
            return value
    canonical_id = row.get("canonical_id") or row.get("agency_id")
    if canonical_id:
        return f"org.ent.pressagency.{canonical_id}"
    return ""


def import_runtime() -> tuple[Any, Any, Any]:
    load_dotenv_if_available()
    try:
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "News-agency snippet scoring requires torch and transformers. "
            "Install the workbench HF extras first."
        ) from exc
    return torch, AutoModelForTokenClassification, AutoTokenizer


def device_for(name: str, torch: Any) -> Any:
    if name == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(name)


def labels_to_spans(labels: list[str], confidences: list[float], margins: list[float]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    start: int | None = None
    active = ""
    active_scores: list[float] = []
    active_margins: list[float] = []

    def close(stop: int) -> None:
        nonlocal start, active, active_scores, active_margins
        if start is not None:
            spans.append(
                {
                    "token_start": start,
                    "token_stop": stop,
                    "label": active,
                    "confidence": min(active_scores) if active_scores else 0.0,
                    "margin": min(active_margins) if active_margins else 0.0,
                }
            )
        start = None
        active = ""
        active_scores = []
        active_margins = []

    for index, label in enumerate(labels):
        if label == "O":
            close(index)
            continue
        base = label[2:] if label.startswith(("B-", "I-")) else label
        prefix = label[:1] if label.startswith(("B-", "I-")) else "B"
        if prefix == "B" or start is None or active != base:
            close(index)
            start = index
            active = base
            active_scores = [confidences[index]]
            active_margins = [margins[index]]
        else:
            active_scores.append(confidences[index])
            active_margins.append(margins[index])
    close(len(labels))
    return spans


def select_suggested_label(
    probabilities: list[float], id2label: dict[int, str] | dict[str, str], non_o_min_confidence: float
) -> tuple[str, float, float]:
    ranked = sorted(range(len(probabilities)), key=lambda index: probabilities[index], reverse=True)
    top = ranked[0]
    top_label = str(id2label.get(top, id2label.get(str(top), "O")))
    selected = top
    if top_label == "O":
        selected = next(
            (
                index
                for index in ranked[1:]
                if str(id2label.get(index, id2label.get(str(index), "O"))) != "O"
                and probabilities[index] > non_o_min_confidence
            ),
            top,
        )
    selected_label = str(id2label.get(selected, id2label.get(str(selected), "O")))
    competitor = next((index for index in ranked if index != selected), selected)
    margin = probabilities[selected] - probabilities[competitor] if competitor != selected else probabilities[selected]
    return selected_label, probabilities[selected], margin


def score_tokens(
    tokens: list[str],
    tokenizer: Any,
    model: Any,
    torch: Any,
    device: Any,
    max_length: int,
    non_o_min_confidence: float = 0.33,
) -> tuple[list[str], list[float], list[float]]:
    encoding = tokenizer(
        tokens,
        is_split_into_words=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )
    word_ids = encoding.word_ids(batch_index=0)
    model_inputs = {key: value.to(device) for key, value in encoding.items()}
    with torch.no_grad():
        logits = model(**model_inputs).logits[0]
        log_probs = torch.log_softmax(logits, dim=-1).detach().cpu()
        probs = torch.softmax(logits, dim=-1).detach().cpu()

    id2label = model.config.id2label
    decoder = str(getattr(model.config, "subtoken_decoding", DECODER_FIRST_SUBTOKEN))
    labels = ["O"] * len(tokens)
    confidences = [0.0] * len(tokens)
    margins = [0.0] * len(tokens)
    word_subtoken_log_probs: list[list[list[float]]] = [[] for _token in tokens]
    first_subtoken_index_by_word: dict[int, int] = {}
    seen_words: set[int] = set()
    for token_index, word_id in enumerate(word_ids):
        if word_id is None or word_id >= len(tokens):
            continue
        word_subtoken_log_probs[word_id].append(log_probs[token_index].tolist())
        if word_id in seen_words:
            continue
        seen_words.add(word_id)
        first_subtoken_index_by_word[word_id] = token_index
        probability_values = [float(value) for value in probs[token_index].tolist()]
        label, confidence, margin = select_suggested_label(
            probability_values, id2label, non_o_min_confidence
        )
        labels[word_id] = label
        confidences[word_id] = confidence
        margins[word_id] = margin
    if (
        decoder == DECODER_FIRST_SUBTOKEN_VITERBI
        and decode_document is not None
        and compile_bio_schema is not None
        and semantic_label_probability is not None
        and semantic_label_margin is not None
    ):
        normalized_id2label = {int(index): str(label) for index, label in id2label.items()}
        decoder_schema = compile_bio_schema(normalized_id2label)
        decoded_ids = decode_document(
            [subtokens or [[0.0] + [-1.0e9 for _label in range(len(normalized_id2label) - 1)]] for subtokens in word_subtoken_log_probs],
            decoder=decoder,
            schema=decoder_schema,
        )
        for word_id, decoded_id in enumerate(decoded_ids):
            label = normalized_id2label[int(decoded_id)]
            labels[word_id] = label
            first_subtoken_index = first_subtoken_index_by_word.get(word_id)
            if first_subtoken_index is None:
                continue
            log_probability_values = [float(value) for value in log_probs[first_subtoken_index].tolist()]
            confidences[word_id] = semantic_label_probability(log_probability_values, int(decoded_id), decoder_schema)
            margins[word_id] = semantic_label_margin(log_probability_values, int(decoded_id), decoder_schema)
    return labels, confidences, margins


def attach_surfaces(spans: list[dict[str, Any]], tokens: list[str], starts: list[int], stops: list[int], text: str) -> list[dict[str, Any]]:
    out = []
    for span in spans:
        start = int(span["token_start"])
        stop = int(span["token_stop"])
        if start >= len(tokens) or stop <= start:
            continue
        char_start = starts[start]
        char_stop = stops[stop - 1]
        item = dict(span)
        item["surface"] = text[char_start:char_stop]
        item["start"] = char_start
        item["stop"] = char_stop
        out.append(item)
    return out


def is_unclosed_dotted_acronym(tokens: list[str], start: int, stop: int) -> bool:
    span_tokens = tokens[start:stop]
    if len(span_tokens) < 3 or len(span_tokens) % 2 == 0:
        return False
    for offset, token in enumerate(span_tokens):
        if offset % 2 == 0:
            if len(token) != 1 or not token.isalpha():
                return False
        elif token != ".":
            return False
    return True


def normalize_dotted_acronym_spans(
    spans: list[dict[str, Any]],
    tokens: list[str],
    starts: list[int],
    stops: list[int],
    text: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for span in spans:
        start = int(span["token_start"])
        stop = int(span["token_stop"])
        item = dict(span)
        if not any(char.isalnum() for char in str(item.get("surface", ""))):
            continue
        if stop < len(tokens) and tokens[stop] == "." and is_unclosed_dotted_acronym(tokens, start, stop):
            stop += 1
            item["token_stop"] = stop
            item["stop"] = stops[stop - 1]
            item["surface"] = text[starts[start] : stops[stop - 1]]
            item["boundary_normalization"] = "include_final_dotted_acronym_period"
        normalized.append(item)

    return suppress_contained_same_label_spans(normalized)


def suppress_contained_same_label_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, span in enumerate(spans):
        start = int(span["token_start"])
        stop = int(span["token_stop"])
        label = str(span.get("label", ""))
        contained = False
        for other_index, other in enumerate(spans):
            if index == other_index or str(other.get("label", "")) != label:
                continue
            other_start = int(other["token_start"])
            other_stop = int(other["token_stop"])
            if other_start <= start and stop <= other_stop and (other_start, other_stop) != (start, stop):
                contained = True
                break
        if not contained:
            out.append(span)
    return out


def suppress_overlapping_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        enumerate(spans),
        key=lambda item: (
            -(int(item[1]["token_stop"]) - int(item[1]["token_start"])),
            -float(item[1].get("confidence") or 0.0),
            -float(item[1].get("margin") or 0.0),
            item[0],
        ),
    )
    kept: list[tuple[int, dict[str, Any]]] = []
    for original_index, span in ranked:
        start = int(span["token_start"])
        stop = int(span["token_stop"])
        if any(start < int(other["token_stop"]) and int(other["token_start"]) < stop for _, other in kept):
            continue
        kept.append((original_index, span))
    return [span for _, span in sorted(kept)]


def merge_adjacent_same_label_spans(spans: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda span: (int(span["token_start"]), int(span["token_stop"])))
    merged: list[dict[str, Any]] = []
    for span in ordered:
        item = dict(span)
        if not merged:
            merged.append(item)
            continue
        previous = merged[-1]
        if (
            str(previous.get("label", "")) == str(item.get("label", ""))
            and int(previous["token_stop"]) == int(item["token_start"])
        ):
            components = list(previous.get("merged_components") or [dict(previous)])
            components.extend(item.get("merged_components") or [dict(item)])
            previous["token_stop"] = int(item["token_stop"])
            previous["stop"] = int(item["stop"])
            previous["surface"] = text[int(previous["start"]) : int(previous["stop"])]
            previous["confidence"] = min(
                float(previous.get("confidence", 0.0)), float(item.get("confidence", 0.0))
            )
            previous["margin"] = min(float(previous.get("margin", 0.0)), float(item.get("margin", 0.0)))
            previous["matcher"] = "adjacent_same_label_merge"
            previous["merged_components"] = components
            continue
        merged.append(item)
    return merged


def is_high_confidence_span(span: dict[str, Any], *, min_confidence: float, min_margin: float) -> bool:
    return float(span.get("confidence", 0.0)) >= min_confidence and float(span.get("margin", 0.0)) >= min_margin


def curation_status(
    row: dict[str, Any],
    spans: list[dict[str, Any]],
    *,
    min_confidence: float,
    min_margin: float,
    multiple_min_confidence: float = 0.99,
    auto_accept: bool = False,
) -> tuple[str, list[str]]:
    target = candidate_label(row)
    reasons: list[str] = []
    if not spans:
        return "needs_review", ["no_predicted_media_source_span"]

    if target:
        matching = [span for span in spans if span["label"] == target]
        if not matching:
            reasons.append("predicted_label_differs_from_candidate")
        spans_to_check = matching or spans
    else:
        spans_to_check = spans
        reasons.append("missing_candidate_label")

    best = max(spans_to_check, key=lambda span: (float(span["confidence"]), float(span["margin"])))
    if float(best["confidence"]) < min_confidence:
        reasons.append("low_confidence")
    if float(best["margin"]) < min_margin:
        reasons.append("low_margin")
    if best["surface"].strip().lower() in {"agence", "agentur", "agency", "ag."}:
        reasons.append("generic_surface_only")
    if len(spans) > 1 and not all(is_high_confidence_span(span, min_confidence=multiple_min_confidence, min_margin=min_margin) for span in spans):
        reasons.append("multiple_predicted_spans")
    if not reasons and not auto_accept:
        reasons.append("manual_review_required")
    return ("auto_accepted" if not reasons else "needs_review"), reasons


def nearby_jsonl_files(path: Path) -> list[Path]:
    parent = path.parent
    if not parent.is_dir():
        return []
    return sorted(item for item in parent.glob("*.jsonl") if item.is_file())


def input_help(path: Path) -> str:
    alternatives = nearby_jsonl_files(path)
    existing_candidate = alternatives[0] if alternatives else path
    lines = [
        "Next steps:",
        "  - Create real search snippets:",
        "      make sample-media-snippets MEDIA_FAMILY=pressagency",
        "  - Or score an existing candidate file:",
        f"      make suggest-media-snippet-spans MEDIA_FAMILY=pressagency MEDIA_SNIPPETS={existing_candidate}",
    ]
    if alternatives:
        lines.extend(["", f"JSONL files currently present in {path.parent}:"])
        lines.extend(f"  - {candidate}" for candidate in alternatives)
    return "\n".join(lines)


def load_input_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Input JSONL does not exist: {path}\n\n{input_help(path)}")
    if not path.is_file():
        raise SystemExit(f"Input path is not a file: {path}\n\n{input_help(path)}")
    if path.stat().st_size == 0:
        raise SystemExit(f"Input JSONL is empty: {path}\n\n{input_help(path)}")
    rows = load_jsonl(path)
    if not rows:
        raise SystemExit(f"Input JSONL has no non-empty rows: {path}\n\n{input_help(path)}")
    return rows


def load_model_runtime(args: argparse.Namespace) -> tuple[Any, Any, Any, Any, str] | None:
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


def validate_model_inference_metadata(config: Any, model_name: str) -> None:
    required = ("annotation_tokenization", "label_all_tokens", "subtoken_labeling", "subtoken_decoding")
    missing = [field for field in required if not hasattr(config, field)]
    if missing:
        raise ValueError(
            f"model {model_name!r} lacks inference metadata: {', '.join(missing)}; "
            "run `make stamp-model-inference-metadata` for a local checkpoint"
        )
    supported_decoders = {DECODER_FIRST_SUBTOKEN, DECODER_FIRST_SUBTOKEN_VITERBI}
    if str(config.subtoken_decoding) not in supported_decoders:
        raise ValueError(f"model {model_name!r} uses unsupported subtoken decoding: {config.subtoken_decoding!r}")


def known_entity_alias_spans(tokens: list[str], starts: list[int], stops: list[int], text: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    from .score_radiostation_snippets import (
        attach_offsets,
        dedupe_spans,
        find_all_press_alias_spans,
        find_all_seed_alias_spans,
        load_pressagency_metadata,
        load_station_metadata,
    )

    radiostations_path = Path(getattr(args, "radiostations", "resources/radiostation_seeds.json"))
    newsagencies_path = Path(getattr(args, "newsagencies", "resources/newsagency_seeds.json"))
    newspapers_path = Path(getattr(args, "newspapers", "resources/newspaper_seeds.json"))
    radiostation_metadata = load_station_metadata(radiostations_path) if radiostations_path.is_file() else {}
    press_metadata = load_pressagency_metadata(newsagencies_path) if newsagencies_path.is_file() else {}
    newspaper_metadata = load_generic_label_metadata(newspapers_path, expected_prefix="org.ent.newspaper.")
    token_spans = []
    token_spans.extend(find_all_seed_alias_spans(tokens, radiostation_metadata))
    token_spans.extend(find_all_press_alias_spans(tokens, press_metadata))
    token_spans.extend(all_generic_alias_spans(tokens, newspaper_metadata))
    return attach_offsets(dedupe_spans(token_spans), starts, stops, text)


def known_entity_scorers(args: argparse.Namespace) -> list[str]:
    scorers = ["radiostation_alias_matcher", "pressagency_alias_matcher"]
    newspapers_path = Path(getattr(args, "newspapers", "resources/newspaper_seeds.json"))
    if newspapers_path.is_file():
        scorers.append("newspaper_alias_matcher")
    return scorers


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


def load_generic_label_metadata(path: Path, *, expected_prefix: str) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    metadata: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return metadata
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "")
        if label.startswith(expected_prefix):
            metadata[label] = row
    return metadata


def all_generic_alias_spans(tokens: list[str], metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    from .score_radiostation_snippets import find_alias_spans, seed_aliases

    spans = []
    for seed in metadata.values():
        label = str(seed.get("label") or "")
        if not label:
            continue
        spans.extend(find_alias_spans(tokens, seed_aliases(seed), label))
    return spans


def score_rows(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input)
    rows_in = load_input_rows(input_path)
    newsagencies_path = Path(getattr(args, "newsagencies", "resources/newsagency_seeds.json"))
    radiostations_path = Path(getattr(args, "radiostations", "resources/radiostation_seeds.json"))
    label_metadata = {}
    label_metadata.update(load_generic_label_metadata(newsagencies_path, expected_prefix="org.ent.pressagency."))
    label_metadata.update(load_generic_label_metadata(radiostations_path, expected_prefix="org.ent.radiostation."))

    model_runtime = load_model_runtime(args)

    rows = []
    counts = {"auto_accepted": 0, "needs_review": 0}
    for index, row in enumerate(rows_in, start=1):
        text, tokens, starts, stops = candidate_tokens(row)
        alias_spans = known_entity_alias_spans(tokens, starts, stops, text, args)
        model_spans: list[dict[str, Any]] = []
        if model_runtime is not None:
            torch, tokenizer, model, device, _model_name = model_runtime
            labels, confidences, margins = score_tokens(
                tokens,
                tokenizer,
                model,
                torch,
                device,
                args.max_sequence_len,
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
            suppress_overlapping_spans(alias_spans + model_spans), text
        )
        label = candidate_label(row) or None
        temporal_verification = verify_entity_start_year(row=row, label=label, label_metadata=label_metadata)
        status, reasons = curation_status(
            row,
            spans,
            min_confidence=args.auto_accept_min_confidence,
            min_margin=args.auto_accept_min_margin,
            multiple_min_confidence=args.auto_accept_multiple_min_confidence,
            auto_accept=bool(getattr(args, "auto_accept", False)),
        )
        if temporal_verification["status"] == "suspicious_before_start":
            reasons.append("suspicious_before_entity_start")
            status = "needs_review"
        out = dict(row)
        out["id"] = candidate_id(row, index)
        out["text"] = text
        out["tokens"] = tokens
        out["token_start_offsets"] = starts
        out["token_end_offsets"] = stops
        out["model"] = {
            "repo_id": args.model,
            "suggest_non_o_min_confidence": float(getattr(args, "suggest_non_o_min_confidence", 0.33)),
            "scorers": known_entity_scorers(args) + (["token_classifier"] if model_runtime is not None else []),
            "predicted_spans": spans,
        }
        out["temporal_verification"] = temporal_verification
        out["curation"] = {
            "status": status,
            "label": label,
            "reasons": reasons,
            "reviewer": None,
            "reviewed_at": None,
            "notes": None,
        }
        if status == "auto_accepted" and spans:
            out["accepted_spans"] = spans
        counts[status] += 1
        rows.append(out)

    write_jsonl(Path(args.output), rows)
    return {"rows": len(rows), **counts, "output": args.output}


def probability(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Suggest known media-source spans in sampled press-agency snippets.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--newsagencies", default="resources/newsagency_seeds.json")
    parser.add_argument("--radiostations", default="resources/radiostation_seeds.json")
    parser.add_argument("--newspapers", default="resources/newspaper_seeds.json")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-sequence-len", type=int, default=512)
    parser.add_argument("--suggest-non-o-min-confidence", type=probability, default=0.33)
    parser.add_argument("--auto-accept-min-confidence", type=probability, default=0.99)
    parser.add_argument("--auto-accept-min-margin", type=probability, default=0.30)
    parser.add_argument("--auto-accept-multiple-min-confidence", type=probability, default=0.99)
    parser.add_argument("--auto-accept", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(json.dumps(score_rows(args), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
