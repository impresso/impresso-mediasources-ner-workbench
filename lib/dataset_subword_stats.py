from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[int(fraction * (len(ordered) - 1))]


def fixed_word_windows(rows: list[dict[str, Any]], *, max_words: int, stride_words: int) -> list[tuple[int, int, list[str]]]:
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    step = max_words - stride_words
    if stride_words < 0 or step <= 0:
        raise ValueError("stride_words must be non-negative and smaller than max_words")
    windows = []
    for doc_index, row in enumerate(rows):
        tokens = [str(token) for token in row.get("tokens") or []]
        start = 0
        while start < len(tokens):
            stop = min(start + max_words, len(tokens))
            windows.append((doc_index, start, tokens[start:stop]))
            if stop == len(tokens):
                break
            start += step
    return windows


def analyze_split(
    rows: list[dict[str, Any]],
    tokenizer: Any,
    *,
    max_words: int,
    stride_words: int,
    sequence_lengths: list[int],
) -> dict[str, Any]:
    word_piece_counts = [
        len(tokenizer(token, add_special_tokens=False)["input_ids"])
        for row in rows
        for token in row.get("tokens") or []
    ]
    windows = fixed_word_windows(rows, max_words=max_words, stride_words=stride_words)
    encoded_windows = [
        tokenizer(tokens, is_split_into_words=True, truncation=False)
        for _doc_index, _start, tokens in windows
    ]
    window_lengths = [len(encoding["input_ids"]) for encoding in encoded_windows]
    thresholds = {}
    for sequence_length in sequence_lengths:
        covered = {doc_index: set() for doc_index in range(len(rows))}
        truncated_windows = 0
        for doc_index, start_word, tokens in windows:
            encoding = tokenizer(
                tokens,
                is_split_into_words=True,
                truncation=True,
                max_length=sequence_length,
            )
            word_ids = {word_id for word_id in encoding.word_ids() if word_id is not None}
            if len(word_ids) < len(tokens):
                truncated_windows += 1
            covered[doc_index].update(start_word + int(word_id) for word_id in word_ids)
        uncovered_by_doc = [
            len(row.get("tokens") or []) - len(covered[doc_index])
            for doc_index, row in enumerate(rows)
        ]
        thresholds[str(sequence_length)] = {
            "windows_over_limit": sum(length > sequence_length for length in window_lengths),
            "truncated_windows": truncated_windows,
            "documents_with_uncovered_words": sum(count > 0 for count in uncovered_by_doc),
            "uncovered_words": sum(uncovered_by_doc),
        }
    return {
        "documents": len(rows),
        "words": len(word_piece_counts),
        "subwords_per_word": {
            "mean": round(statistics.mean(word_piece_counts), 3) if word_piece_counts else 0.0,
            "p50": percentile(word_piece_counts, 0.50) if word_piece_counts else 0,
            "p90": percentile(word_piece_counts, 0.90) if word_piece_counts else 0,
            "p95": percentile(word_piece_counts, 0.95) if word_piece_counts else 0,
            "p99": percentile(word_piece_counts, 0.99) if word_piece_counts else 0,
            "max": max(word_piece_counts, default=0),
        },
        "windows": {
            "max_words": max_words,
            "stride_words": stride_words,
            "count": len(windows),
            "subwords": {
                "p50": percentile(window_lengths, 0.50) if window_lengths else 0,
                "p90": percentile(window_lengths, 0.90) if window_lengths else 0,
                "p95": percentile(window_lengths, 0.95) if window_lengths else 0,
                "p99": percentile(window_lengths, 0.99) if window_lengths else 0,
                "max": max(window_lengths, default=0),
            },
            "sequence_lengths": thresholds,
        },
    }


def parse_split(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or not name or not raw_path:
        raise argparse.ArgumentTypeError(f"expected NAME=PATH, got {value!r}")
    return name, Path(raw_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect tokenizer subword and fixed-word-window statistics for JSONL datasets.")
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--split", action="append", required=True, type=parse_split)
    parser.add_argument("--max-words-per-window", type=int, default=256)
    parser.add_argument("--stride-words", type=int, default=32)
    parser.add_argument("--sequence-length", action="append", type=int, default=[])
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    sequence_lengths = sorted(set(args.sequence_length or [512, 1024]))
    report = {
        "tokenizer": args.tokenizer,
        "max_words_per_window": args.max_words_per_window,
        "stride_words": args.stride_words,
        "sequence_lengths": sequence_lengths,
        "splits": {
            name: analyze_split(
                load_jsonl(path),
                tokenizer,
                max_words=args.max_words_per_window,
                stride_words=args.stride_words,
                sequence_lengths=sequence_lengths,
            )
            for name, path in args.split
        },
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
