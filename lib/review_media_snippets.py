from __future__ import annotations

import argparse


SUPPORTED_FAMILIES = {"pressagency", "radiostation", "newspaper"}


def strip_family(argv: list[str] | None) -> list[str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--family", choices=sorted(SUPPORTED_FAMILIES), required=True)
    _args, rest = parser.parse_known_args(argv)
    return rest


def main(argv: list[str] | None = None) -> int:
    from .review_newsagency_snippets import main as review_main

    return review_main(strip_family(argv))


if __name__ == "__main__":
    raise SystemExit(main())
