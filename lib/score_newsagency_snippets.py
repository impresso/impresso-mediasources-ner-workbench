from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .snippet_data import candidate_id, candidate_tokens, load_jsonl, write_jsonl

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


def score_tokens(tokens: list[str], tokenizer: Any, model: Any, torch: Any, device: Any, max_length: int) -> tuple[list[str], list[float], list[float]]:
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
        probs = torch.softmax(logits, dim=-1).detach().cpu()

    id2label = model.config.id2label
    labels = ["O"] * len(tokens)
    confidences = [0.0] * len(tokens)
    margins = [0.0] * len(tokens)
    seen_words: set[int] = set()
    for token_index, word_id in enumerate(word_ids):
        if word_id is None or word_id in seen_words or word_id >= len(tokens):
            continue
        seen_words.add(word_id)
        ranked = torch.topk(probs[token_index], k=min(2, probs.shape[-1]))
        label_id = int(ranked.indices[0].item())
        labels[word_id] = str(id2label[label_id])
        confidences[word_id] = float(ranked.values[0].item())
        margins[word_id] = float(ranked.values[0].item() - ranked.values[1].item()) if len(ranked.values) > 1 else float(ranked.values[0].item())
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


def is_high_confidence_span(span: dict[str, Any], *, min_confidence: float, min_margin: float) -> bool:
    return float(span.get("confidence", 0.0)) >= min_confidence and float(span.get("margin", 0.0)) >= min_margin


def curation_status(
    row: dict[str, Any],
    spans: list[dict[str, Any]],
    *,
    min_confidence: float,
    min_margin: float,
    multiple_min_confidence: float = 0.99,
) -> tuple[str, list[str]]:
    target = candidate_label(row)
    reasons: list[str] = []
    if not spans:
        return "needs_review", ["no_predicted_pressagency_span"]

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
        "      make sample-newsagencies PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk",
        "  - Or score an existing candidate file:",
        f"      make score-newsagency-snippets NEWSAGENCY_SNIPPETS={existing_candidate}",
        "  - Or build legacy-derived bootstrap snippets first:",
        "      make build-newsagency-snippets-from-legacy PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk",
        f"      make score-newsagency-snippets NEWSAGENCY_SNIPPETS={DEFAULT_LEGACY_SNIPPETS}",
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


def score_rows(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input)
    rows_in = load_input_rows(input_path)

    torch, model_cls, tokenizer_cls = import_runtime()
    model_ref = resolve_model_ref(args.model)
    device = device_for(args.device, torch)
    tokenizer = tokenizer_cls.from_pretrained(model_ref)
    model = model_cls.from_pretrained(model_ref).to(device)
    model.eval()

    rows = []
    counts = {"auto_accepted": 0, "needs_review": 0}
    for index, row in enumerate(rows_in, start=1):
        text, tokens, starts, stops = candidate_tokens(row)
        labels, confidences, margins = score_tokens(tokens, tokenizer, model, torch, device, args.max_sequence_len)
        spans = normalize_dotted_acronym_spans(
            attach_surfaces(labels_to_spans(labels, confidences, margins), tokens, starts, stops, text),
            tokens,
            starts,
            stops,
            text,
        )
        status, reasons = curation_status(
            row,
            spans,
            min_confidence=args.auto_accept_min_confidence,
            min_margin=args.auto_accept_min_margin,
            multiple_min_confidence=args.auto_accept_multiple_min_confidence,
        )
        out = dict(row)
        out["id"] = candidate_id(row, index)
        out["text"] = text
        out["tokens"] = tokens
        out["token_start_offsets"] = starts
        out["token_end_offsets"] = stops
        out["model"] = {
            "repo_id": args.model,
            "predicted_spans": spans,
        }
        out["curation"] = {
            "status": status,
            "label": candidate_label(row) or None,
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score sampled news-agency snippets with the current NER model.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-sequence-len", type=int, default=512)
    parser.add_argument("--auto-accept-min-confidence", type=float, default=0.99)
    parser.add_argument("--auto-accept-min-margin", type=float, default=0.30)
    parser.add_argument("--auto-accept-multiple-min-confidence", type=float, default=0.99)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(json.dumps(score_rows(args), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
