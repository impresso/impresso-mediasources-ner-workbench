"""Interactive Impresso semantic-search and chunk-refinement prototype."""

from __future__ import annotations

import argparse
import base64
import math
import struct
from dataclasses import dataclass
from typing import Any, Callable, Sequence


APP_CONTENT_URL = "https://impresso-project.ch/app/content-item/{document_id}"
DEV_APP_CONTENT_URL = "https://dev.impresso-project.ch/app/content-item/{document_id}"
DEV_API_URL = "https://dev.impresso-project.ch/public-api/v1"


@dataclass(frozen=True)
class TextChunk:
    start: int
    end: int
    text: str
    score: float = 0.0


def decode_embedding(value: str) -> list[float]:
    """Decode Impresso's ``model:base64-float32`` embedding representation."""
    encoded = value.split(":", 1)[-1]
    payload = base64.b64decode(encoded)
    if not payload or len(payload) % 4:
        raise ValueError("embedding payload is not a non-empty float32 vector")
    return list(struct.unpack(f"<{len(payload) // 4}f", payload))


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError(f"embedding dimensions differ: {len(left)} != {len(right)}")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def embedding_details(value: str) -> dict[str, Any]:
    vector = decode_embedding(value)
    model, separator, _ = value.partition(":")
    return {
        "model": model if separator else "<unprefixed>",
        "dimensions": len(vector),
        "norm": math.sqrt(sum(item * item for item in vector)),
        "preview": vector[:6],
        "encoded_characters": len(value),
    }


def word_chunks(words: Sequence[str], size: int, overlap: float) -> list[TextChunk]:
    if size < 1:
        raise ValueError("chunk size must be positive")
    if not 0 <= overlap < 1:
        raise ValueError("overlap must be in [0, 1)")
    if not words:
        return []
    if len(words) <= size:
        return [TextChunk(0, len(words), " ".join(words))]
    step = max(1, round(size * (1 - overlap)))
    starts = list(range(0, len(words) - size + 1, step))
    final_start = len(words) - size
    if starts[-1] != final_start:
        starts.append(final_start)
    chunks = [
        TextChunk(start, min(start + size, len(words)), " ".join(words[start : start + size]))
        for start in starts
    ]
    return chunks


def refine_text(
    text: str,
    query_vector: Sequence[float],
    embed_text: Callable[[str], str],
    *,
    initial_words: int = 180,
    min_words: int = 30,
    rounds: int = 3,
    overlap: float = 0.25,
) -> list[TextChunk]:
    """Select the best chunk, then repeatedly refine only that region."""
    region_words = text.split()
    region_start = 0
    selected: list[TextChunk] = []
    chunk_size = min(initial_words, len(region_words))
    for _ in range(rounds):
        if not region_words:
            break
        candidates = word_chunks(region_words, max(min_words, chunk_size), overlap)
        scored = [
            TextChunk(
                start=region_start + chunk.start,
                end=region_start + chunk.end,
                text=chunk.text,
                score=cosine_similarity(query_vector, decode_embedding(embed_text(chunk.text))),
            )
            for chunk in candidates
        ]
        best = max(scored, key=lambda chunk: chunk.score)
        selected.append(best)
        if best.end - best.start <= min_words:
            break
        absolute_words = text.split()
        region_words = absolute_words[best.start : best.end]
        region_start = best.start
        chunk_size = max(min_words, math.ceil((best.end - best.start) / 2))
    return selected


def _full_text(row: dict[str, Any]) -> str:
    text = row.get("text") or {}
    return str(text.get("content") or "").strip()


def _summary(row: dict[str, Any]) -> str:
    text = row.get("text") or {}
    meta = row.get("meta") or {}
    title = text.get("title") or "<untitled>"
    date = str(meta.get("date") or "")[:10]
    source = meta.get("mediaId") or meta.get("mediaTitle") or "?"
    score = row.get("relevanceScore")
    score_text = f" similarity={score:.4f}" if isinstance(score, (int, float)) else ""
    return f"{row.get('id')} | {source} {date} | {title}{score_text}"


def _resolve_api_url(args: argparse.Namespace) -> str | None:
    if args.api_url:
        return args.api_url
    if args.environment == "dev":
        return DEV_API_URL
    return None


def _content_url(args: argparse.Namespace, document_id: str) -> str:
    template = DEV_APP_CONTENT_URL if args.environment == "dev" else APP_CONTENT_URL
    return template.format(document_id=document_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explore Impresso semantic search and recursively narrow article text."
    )
    parser.add_argument("--environment", choices=("normal", "dev"), default="normal")
    parser.add_argument("--api-url", help="Explicit API URL; overrides --environment")
    parser.add_argument("--query", help="Semantic query; otherwise prompt for one line")
    parser.add_argument("--language", help="Optional two-letter language filter")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--initial-chunk-words", type=int, default=180)
    parser.add_argument("--min-chunk-words", type=int, default=30)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--overlap", type=float, default=0.25)
    parser.add_argument(
        "--no-persist-token",
        action="store_true",
        help="Prompt for a token without storing it in ~/.impresso_py.yml",
    )
    return parser


def interactive(args: argparse.Namespace) -> int:
    from impresso import connect

    client = connect(
        public_api_url=_resolve_api_url(args),
        persisted_token=not args.no_persist_token,
    )
    query = (args.query or input("Semantic search text: ")).strip()
    if not query or query.lower() in {"q", "quit"}:
        return 0
    print("Embedding query...", flush=True)
    query_embedding = client.tools.embed_text(text=query, target="text")
    query_vector = decode_embedding(query_embedding)
    details = embedding_details(query_embedding)
    print(
        "Embedding: "
        f"target=text model={details['model']} dimensions={details['dimensions']} "
        f"norm={details['norm']:.6f} encoded_characters={details['encoded_characters']}"
    )
    print("Embedding preview: " + " ".join(f"{value:.6f}" for value in details["preview"]))
    print(f"Searching for the {args.limit} nearest content items...", flush=True)
    print(
        f"Search request: api={client.api_url} language={args.language or '<any>'} "
        f"limit={args.limit} with_text_contents=false"
    )
    result = client.search.find(
        embedding=query_embedding,
        language=args.language,
        limit=args.limit,
    )
    rows = list(result.raw.get("data", []))
    pagination = result.raw.get("pagination") or {}
    print(
        f"Search response: rows={len(rows)} total={pagination.get('total', result.total)} "
        f"offset={pagination.get('offset', result.offset)} limit={pagination.get('limit', result.limit)}"
    )
    if result.url:
        print(f"Search URL: {result.url}")
    if not rows:
        print(
            "No results for this request. The embedding was generated successfully; "
            "the empty response therefore comes from search availability or the active language filter."
        )
        return 0
    print(f"\nTop {len(rows)} results:")
    for index, row in enumerate(rows, 1):
        print(f"  {index}. {_summary(row)}")
        print(f"     {_content_url(args, str(row.get('id')))}")
    while True:
        choice = input(
            f"Narrow result [1-{len(rows)}, a=all, Enter=1, q=quit]> "
        ).strip().lower()
        if choice in {"q", "quit"}:
            return 0
        try:
            indexes = list(range(len(rows))) if choice == "a" else [int(choice or "1") - 1]
            if any(index < 0 or index >= len(rows) for index in indexes):
                raise ValueError
        except ValueError:
            print(f"Choose 1-{len(rows)}, a, or q.")
            continue
        break
    for index in indexes:
        row = rows[index]
        print(f"\nRetrieving full text for result {index + 1}...", flush=True)
        text = _full_text(row)
        if not text:
            text = _full_text(client.content_items.get(str(row["id"])).raw)
        if not text:
            print(f"{index + 1}. Full text is unavailable.")
            continue
        print(f"Refining the closest passage in {len(text.split())} words...", flush=True)
        levels = refine_text(
            text,
            query_vector,
            lambda chunk: client.tools.embed_text(text=chunk, target="text"),
            initial_words=args.initial_chunk_words,
            min_words=args.min_chunk_words,
            rounds=args.rounds,
            overlap=args.overlap,
        )
        print(f"\n{index + 1}. {_summary(row)}")
        for level, chunk in enumerate(levels, 1):
            print(
                f"  level {level}: words={chunk.start}:{chunk.end} "
                f"similarity={chunk.score:.4f}"
            )
        if levels:
            print("-" * 80)
            print(levels[-1].text)
            print("-" * 80)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit < 1 or args.rounds < 1:
        raise SystemExit("--limit and --rounds must be positive")
    if args.min_chunk_words < 1 or args.initial_chunk_words < args.min_chunk_words:
        raise SystemExit("chunk sizes must be positive and initial must be >= minimum")
    if not 0 <= args.overlap < 1:
        raise SystemExit("--overlap must be in [0, 1)")
    try:
        return interactive(args)
    except (KeyboardInterrupt, EOFError):
        print()
        return 130
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
