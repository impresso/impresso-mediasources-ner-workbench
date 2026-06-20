from __future__ import annotations

import argparse


SUPPORTED_FAMILIES = {"pressagency", "radiostation"}


def split_family(argv: list[str] | None) -> tuple[str, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--family", choices=sorted(SUPPORTED_FAMILIES), required=True)
    args, rest = parser.parse_known_args(argv)
    return args.family, rest


def main(argv: list[str] | None = None) -> int:
    family, rest = split_family(argv)
    if family == "pressagency":
        from .score_newsagency_snippets import main as family_main

        return family_main(rest)
    if family == "radiostation":
        from .score_radiostation_snippets import main as family_main

        return family_main(rest)
    raise SystemExit(f"unsupported media-source family for span suggestion: {family}")


if __name__ == "__main__":
    raise SystemExit(main())
