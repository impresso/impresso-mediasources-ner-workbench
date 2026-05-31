from __future__ import annotations

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample radio-station candidate mentions from Impresso.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-docs", type=int, default=None)
    parser.add_argument("--out", default="data/candidates/radiostations.jsonl")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        print(f"dry-run: would sample radio-station candidates into {args.out}")
        return 0
    raise NotImplementedError("radio-station sampling is scaffolded but not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
