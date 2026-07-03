import base64
import struct

import pytest

from lib.semantic_search_explorer import (
    cosine_similarity,
    decode_embedding,
    refine_text,
    word_chunks,
)


def encode(values: list[float]) -> str:
    payload = struct.pack(f"<{len(values)}f", *values)
    return "model:" + base64.b64encode(payload).decode("ascii")


def test_decode_embedding_and_cosine_similarity() -> None:
    assert decode_embedding(encode([1.0, 2.0])) == [1.0, 2.0]
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_word_chunks_overlap_and_cover_tail() -> None:
    chunks = word_chunks("a b c d e f g".split(), size=4, overlap=0.5)
    assert [(chunk.start, chunk.end) for chunk in chunks] == [(0, 4), (2, 6), (3, 7)]


def test_refine_text_keeps_narrowing_best_region() -> None:
    text = "zero one two target target five six seven"

    def embed(value: str) -> str:
        return encode([float(value.count("target")), 1.0])

    levels = refine_text(
        text,
        [2.0, 1.0],
        embed,
        initial_words=4,
        min_words=2,
        rounds=2,
        overlap=0.5,
    )

    assert len(levels) == 2
    assert "target target" in levels[0].text
    assert "target" in levels[-1].text
