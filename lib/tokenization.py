from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


TOKENIZATION_PROFILE = "unicode-word-punctuation-v1"
TOKEN_RE = re.compile(r"[^\W\d_]+|\d+|_+|[^\w\s]", re.UNICODE)
FRENCH_ELIDED_AGENCE_RE = re.compile(r"^[lL](['’])(?=[aA]gence\b)")


@dataclass(frozen=True)
class CharacterEntity:
    start: int
    stop: int
    label: str


def tokenize_with_offsets(text: str) -> tuple[list[str], list[int], list[int]]:
    matches = list(TOKEN_RE.finditer(text))
    return (
        [match.group(0) for match in matches],
        [match.start() for match in matches],
        [match.end() for match in matches],
    )


def bio_to_character_entities(row: dict[str, Any]) -> list[CharacterEntity]:
    labels = row["token_labels"]
    starts = row["token_start_offsets"]
    stops = row["token_end_offsets"]
    if not (len(row["tokens"]) == len(labels) == len(starts) == len(stops)):
        raise ValueError(f"{row.get('id')}: token arrays have different lengths")
    entities: list[CharacterEntity] = []
    active_start: int | None = None
    active_stop: int | None = None
    active_label = ""

    def close() -> None:
        nonlocal active_start, active_stop, active_label
        if active_start is not None and active_stop is not None:
            entities.append(CharacterEntity(active_start, active_stop, active_label))
        active_start = active_stop = None
        active_label = ""

    for index, token_label in enumerate(labels):
        if token_label == "O":
            close()
            continue
        prefix, separator, label = str(token_label).partition("-")
        if not separator or prefix not in {"B", "I"}:
            raise ValueError(f"{row.get('id')}: invalid BIO label {token_label!r}")
        if prefix == "B" or active_start is None or active_label != label:
            close()
            active_start = int(starts[index])
            active_label = label
        active_stop = int(stops[index])
    close()
    return entities


def narrow_french_agence(entity: CharacterEntity, text: str) -> tuple[CharacterEntity, bool]:
    if not entity.label.startswith("org.ent.pressagency."):
        return entity, False
    surface = text[entity.start : entity.stop]
    match = FRENCH_ELIDED_AGENCE_RE.match(surface)
    if not match:
        return entity, False
    narrowed = CharacterEntity(entity.start + match.end(), entity.stop, entity.label)
    return narrowed, True


def project_entities_to_bio(
    entities: list[CharacterEntity], starts: list[int], stops: list[int], *, row_id: str
) -> tuple[list[str], list[dict[str, Any]]]:
    labels = ["O"] * len(starts)
    materialized: list[dict[str, Any]] = []
    for entity in entities:
        covered = [
            index
            for index, (start, stop) in enumerate(zip(starts, stops, strict=True))
            if start >= entity.start and stop <= entity.stop
        ]
        if not covered or starts[covered[0]] != entity.start or stops[covered[-1]] != entity.stop:
            raise ValueError(
                f"{row_id}: character entity {entity.start}:{entity.stop} does not align with canonical tokens"
            )
        if covered != list(range(covered[0], covered[-1] + 1)):
            raise ValueError(f"{row_id}: non-contiguous token projection for {entity.start}:{entity.stop}")
        for offset, index in enumerate(covered):
            if labels[index] != "O":
                raise ValueError(f"{row_id}: overlapping entity at canonical token {index}")
            labels[index] = f"{'B' if offset == 0 else 'I'}-{entity.label}"
        materialized.append(
            {
                "token_start": covered[0],
                "token_stop": covered[-1] + 1,
                "start": entity.start,
                "stop": entity.stop,
                "label": entity.label,
            }
        )
    return labels, materialized


def validate_canonical_tokens(text: str, tokens: list[str], starts: list[int], stops: list[int]) -> None:
    expected = tokenize_with_offsets(text)
    if (tokens, starts, stops) != expected:
        raise ValueError("tokens and offsets do not match the canonical tokenization profile")
    for token, start, stop in zip(tokens, starts, stops, strict=True):
        if text[start:stop] != token:
            raise ValueError(f"token offset mismatch for {token!r} at {start}:{stop}")
