from __future__ import annotations

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish or dry-run the Hugging Face held-out testset.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        print("dry-run: would publish held-out testset")
        return 0
    raise NotImplementedError("testset publishing is scaffolded but not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
