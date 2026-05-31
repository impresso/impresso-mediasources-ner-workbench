from __future__ import annotations

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Curate local candidate JSONL files.")
    parser.add_argument("--input", required=False)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        print(f"dry-run: would curate {args.input or '<missing input>'}")
        return 0
    raise NotImplementedError("candidate curation is scaffolded but not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
