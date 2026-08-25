from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_SUBTOKEN_DECODING = "first_subtoken_viterbi"


def dataset_profile(path: Path) -> str:
    profiles = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            profiles.add(str(row.get("tokenization") or ""))
    profiles.discard("")
    if len(profiles) != 1:
        raise ValueError(f"{path}: expected exactly one non-empty tokenization profile, found {sorted(profiles)}")
    return next(iter(profiles))


def stamp_config(path: Path, *, profile: str, label_all_tokens: bool) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    config = json.loads(path.read_text(encoding="utf-8"))
    config["annotation_tokenization"] = profile
    config["label_all_tokens"] = bool(label_all_tokens)
    config["subtoken_labeling"] = "all_subtokens_b_to_i" if label_all_tokens else "first_subtoken_only"
    config["subtoken_decoding"] = DEFAULT_SUBTOKEN_DECODING
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "config": str(path),
        "annotation_tokenization": profile,
        "label_all_tokens": bool(label_all_tokens),
        "subtoken_labeling": config["subtoken_labeling"],
        "subtoken_decoding": config["subtoken_decoding"],
    }


def parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stamp annotation/subtoken policy into a trained model config.")
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--label-all-tokens", required=True, type=parse_bool)
    parser.add_argument("--include-best", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile = dataset_profile(args.dataset)
    configs = [args.model_dir / "config.json"]
    best = args.model_dir / "best" / "config.json"
    if args.include_best and best.is_file():
        configs.append(best)
    results = [stamp_config(path, profile=profile, label_all_tokens=args.label_all_tokens) for path in configs]
    print(json.dumps({"updated": results}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
