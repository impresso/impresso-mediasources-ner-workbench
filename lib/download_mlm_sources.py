from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path


def parse_source(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"expected LANG=URL, got {value!r}")
    lang, url = value.split("=", 1)
    lang = lang.strip()
    url = url.strip()
    if not lang:
        raise argparse.ArgumentTypeError(f"missing language in {value!r}")
    if not url:
        raise argparse.ArgumentTypeError(f"missing URL in {value!r}")
    return lang, url


def download(url: str, destination: Path, *, force: bool) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0 and not force:
        return {"path": str(destination), "status": "exists", "bytes": destination.stat().st_size}

    with tempfile.NamedTemporaryFile(prefix=destination.name + ".", suffix=".part", dir=destination.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        with urllib.request.urlopen(url) as response:
            shutil.copyfileobj(response, tmp)

    if tmp_path.stat().st_size < 3:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded file is unexpectedly small: {url}")
    with tmp_path.open("rb") as handle:
        magic = handle.read(3)
    if magic != b"BZh":
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded file does not look like bzip2 JSONL: {url}")

    tmp_path.replace(destination)
    return {"path": str(destination), "status": "downloaded", "bytes": destination.stat().st_size}


def run(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = Path(args.output_dir)
    results = []
    for lang, url in args.source:
        destination = out_dir / f"{lang}.compiled.jsonl.bz2"
        result = download(url, destination, force=args.force)
        result.update({"language": lang, "url": url})
        results.append(result)
    return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download compiled Impresso source files for continued MLM pretraining.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source", action="append", required=True, type=parse_source, help="Language source as LANG=URL.")
    parser.add_argument("--force", action="store_true", help="Re-download files even when they already exist.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    print(json.dumps(run(args), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
