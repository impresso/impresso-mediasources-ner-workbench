from __future__ import annotations

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export curated media-source data as JSONL.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="data/curated/train.jsonl")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        print(f"dry-run: would export curated training data to {args.out}")
        return 0
    raise NotImplementedError("dataset export is scaffolded but not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
