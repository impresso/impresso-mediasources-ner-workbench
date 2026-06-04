from __future__ import annotations

from pathlib import Path


def load_dotenv_if_available(path: Path = Path(".env")) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(path)
