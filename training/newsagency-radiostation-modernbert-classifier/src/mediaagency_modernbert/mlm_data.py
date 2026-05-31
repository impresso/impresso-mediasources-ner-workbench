from __future__ import annotations

import argparse
import bz2
import json
import random
import re
import sys
from pathlib import Path
from typing import Any


def first_nonempty(*vals: Any) -> Any:
    for value in vals:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
        else:
            return value
    return None


def parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_lb(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                pass
        return out
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parse_lb(parsed)
        out = []
        for part in value.split(","):
            try:
                out.append(int(part.strip()))
            except (TypeError, ValueError):
                pass
        return out
    return []


def apply_linebreak_offsets(text: str, linebreaks: Any) -> str:
    offsets = sorted(set(parse_lb(linebreaks)))
    if not offsets:
        return text
    chars = list(text)
    for pos in offsets:
        if 0 <= pos < len(chars):
            chars[pos] = "\n"
    return "".join(chars)


def normalize_text(text: str, linebreaks: Any) -> str:
    text = apply_linebreak_offsets(text, linebreaks)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for char in ["\u00ad", "\u200b", "\ufeff"]:
        text = text.replace(char, "")
    text = re.sub(r"(?<=\w)[\-‐-‒–]\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def open_jsonl_bz2(path: Path):
    with bz2.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def extract_row(obj: dict[str, Any], fallback_lang: str, *, ocr_min: float, min_chars: int) -> dict[str, Any] | None:
    item_id = first_nonempty(obj.get("id"), obj.get("document_id"), obj.get("ci_id"))
    if not item_id:
        return None
    raw_text = first_nonempty(obj.get("ft"), obj.get("text"), obj.get("content"))
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    ocr_quality = parse_float(first_nonempty(obj.get("ocrQuality"), obj.get("ocr_quality"), obj.get("ocrqa"), obj.get("qa")))
    if ocr_quality is None or ocr_quality < ocr_min:
        return None
    text = normalize_text(raw_text, obj.get("lb"))
    if len(text) < min_chars:
        return None
    return {
        "id": item_id,
        "text": text,
        "date": first_nonempty(obj.get("date"), obj.get("d")),
        "mediaId": first_nonempty(obj.get("mediaId"), obj.get("media_id"), obj.get("newspaper"), obj.get("np")),
        "mediaTitle": first_nonempty(obj.get("mediaTitle"), obj.get("media_title"), obj.get("title"), obj.get("newspaper"), obj.get("np")),
        "language": first_nonempty(obj.get("language"), obj.get("lang"), obj.get("langCode"), fallback_lang),
        "ocrQuality": ocr_quality,
    }


def compute_balanced_targets(counts: dict[str, int], total_target: int) -> dict[str, int]:
    targets = {lang: 0 for lang in counts}
    capacities = counts.copy()
    remaining = total_target
    active = {lang for lang, count in capacities.items() if count > 0}
    while active and remaining > 0:
        share = max(1, remaining // len(active))
        progressed = False
        for lang in list(active):
            take = min(share, capacities[lang])
            if take:
                targets[lang] += take
                capacities[lang] -= take
                remaining -= take
                progressed = True
            if capacities[lang] == 0:
                active.remove(lang)
        if not progressed:
            break
    return targets


def compute_max_per_language_targets(counts: dict[str, int], max_per_language: int | None) -> dict[str, int]:
    if max_per_language is None or max_per_language <= 0:
        return {}
    return {lang: min(count, max_per_language) for lang, count in counts.items()}


def reservoir_sample(path: Path, lang: str, k: int, *, ocr_min: float, min_chars: int, rng: random.Random, progress_interval: int) -> list[dict[str, Any]]:
    reservoir: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    raw_seen = 0
    valid_seen = 0
    for obj in open_jsonl_bz2(path):
        raw_seen += 1
        row = extract_row(obj, lang, ocr_min=ocr_min, min_chars=min_chars)
        if row is None or row["id"] in seen_ids:
            if progress_interval > 0 and raw_seen % progress_interval == 0:
                log(f"[sample:{lang}] rows_read={raw_seen:,} valid_unique={valid_seen:,} selected={len(reservoir):,}/{k:,}")
            continue
        seen_ids.add(row["id"])
        valid_seen += 1
        if len(reservoir) < k:
            reservoir.append(row)
        else:
            j = rng.randint(1, valid_seen)
            if j <= k:
                reservoir[j - 1] = row
        if progress_interval > 0 and raw_seen % progress_interval == 0:
            log(f"[sample:{lang}] rows_read={raw_seen:,} valid_unique={valid_seen:,} selected={len(reservoir):,}/{k:,}")
    log(f"[sample:{lang}] done rows_read={raw_seen:,} valid_unique={valid_seen:,} selected={len(reservoir):,}/{k:,}")
    return reservoir


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_dataset(args: argparse.Namespace) -> dict[str, Any]:
    dataset_dir = Path(args.dataset_dir)
    out_dir = Path(args.output_dir)
    langs = args.languages.split(",") if "," in args.languages else args.languages.split()
    file_map = {lang: dataset_dir / f"{lang}.compiled.jsonl.bz2" for lang in langs}
    for lang, path in file_map.items():
        if not path.exists():
            raise FileNotFoundError(f"missing compiled file for {lang}: {path}")

    log(f"[config] languages={' '.join(langs)}")
    log(f"[config] dataset_dir={dataset_dir}")
    log(f"[config] output_dir={out_dir}")
    log(f"[config] max_per_language={args.max_per_language} target_total={args.target_total} validation_fraction={args.validation_fraction}")
    counts: dict[str, int] = {}
    for lang, path in file_map.items():
        log(f"[count:{lang}] start path={path}")
        seen_ids: set[str] = set()
        raw_seen = 0
        for obj in open_jsonl_bz2(path):
            raw_seen += 1
            row = extract_row(obj, lang, ocr_min=args.ocr_min, min_chars=args.min_chars)
            if row is not None:
                seen_ids.add(row["id"])
            if args.progress_interval > 0 and raw_seen % args.progress_interval == 0:
                log(f"[count:{lang}] rows_read={raw_seen:,} valid_unique={len(seen_ids):,}")
        counts[lang] = len(seen_ids)
        log(f"[count:{lang}] done rows_read={raw_seen:,} valid_unique={counts[lang]:,}")

    targets = compute_max_per_language_targets(counts, args.max_per_language)
    sampling_policy = "max_per_language" if targets else "balanced_total"
    if not targets:
        targets = compute_balanced_targets(counts, args.target_total)
    log(f"[targets] policy={sampling_policy} targets={json.dumps(targets, sort_keys=True)}")
    rng = random.Random(args.seed)
    rows: list[dict[str, Any]] = []
    sampled_by_lang: dict[str, int] = {}
    for lang, path in file_map.items():
        log(f"[sample:{lang}] start target={targets[lang]:,}")
        sampled = reservoir_sample(path, lang, targets[lang], ocr_min=args.ocr_min, min_chars=args.min_chars, rng=rng, progress_interval=args.progress_interval)
        sampled_by_lang[lang] = len(sampled)
        rows.extend(sampled)
    log(f"[shuffle] rows={len(rows):,}")
    rng.shuffle(rows)

    split_idx = int(len(rows) * (1.0 - args.validation_fraction))
    train_rows = rows[:split_idx]
    validation_rows = rows[split_idx:]
    log(f"[write] train={len(train_rows):,} validation={len(validation_rows):,}")
    write_jsonl(out_dir / "train.json", train_rows)
    write_jsonl(out_dir / "validation.json", validation_rows)
    report = {
        "counts": counts,
        "max_per_language": args.max_per_language,
        "sampling_policy": sampling_policy,
        "targets": targets,
        "sampled_by_language": sampled_by_lang,
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "ocr_min": args.ocr_min,
        "min_chars": args.min_chars,
        "progress_interval": args.progress_interval,
        "seed": args.seed,
    }
    (out_dir / "dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log(f"[write] report={out_dir / 'dataset_report.json'}")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build balanced multilingual Impresso MLM JSONL data.")
    parser.add_argument("--dataset-dir", required=True, help="Directory containing <lang>.compiled.jsonl.bz2 files.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--languages", default="fr de en lb")
    parser.add_argument("--target-total", type=int, default=50000)
    parser.add_argument("--max-per-language", type=int, default=0, help="Sample up to this many rows per language. Overrides --target-total when greater than 0.")
    parser.add_argument("--validation-fraction", type=float, default=0.05)
    parser.add_argument("--ocr-min", type=float, default=0.90)
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--progress-interval", type=int, default=100000, help="Emit diagnostics every N input rows. Use 0 to disable progress logs.")
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    print(json.dumps(build_dataset(args), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
