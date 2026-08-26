from __future__ import annotations

from dataclasses import dataclass
from typing import Any


Entity = tuple[int, int, str]


@dataclass(frozen=True)
class EntityAlignment:
    outcome: str
    gold: tuple[Entity, ...]
    predictions: tuple[Entity, ...]


def strip_bio(label: str) -> str:
    if label == "O":
        return "O"
    if label.startswith(("B-", "I-")):
        return label[2:]
    return label


def labels_to_entities(labels: list[str], *, merge_adjacent_same_label: bool = False) -> set[Entity]:
    entities: set[Entity] = set()
    start: int | None = None
    active = ""

    def close(stop: int) -> None:
        nonlocal start, active
        if start is not None:
            entities.add((start, stop, active))
        start = None
        active = ""

    for index, label in enumerate(labels):
        if label == "O":
            close(index)
            continue
        prefix = label[:1] if label.startswith(("B-", "I-")) else "B"
        base = strip_bio(label)
        if start is None or active != base or (prefix == "B" and not merge_adjacent_same_label):
            close(index)
            start = index
            active = base
    close(len(labels))
    return entities


def render_tokens(tokens: list[str], token_render: list[str] | None = None) -> str:
    token_render = token_render or [""] * len(tokens)
    parts = []
    for index, token in enumerate(tokens):
        parts.append(token)
        render = token_render[index] if index < len(token_render) else ""
        if "NoSpaceAfter" not in render and index != len(tokens) - 1:
            parts.append(" ")
    return "".join(parts)


def natural_text(row: dict[str, Any], start: int, stop: int) -> str:
    token_start_offsets = row.get("token_start_offsets", [])
    token_end_offsets = row.get("token_end_offsets", [])
    text = row.get("text")
    if (
        isinstance(text, str)
        and start < len(token_start_offsets)
        and stop > start
        and stop - 1 < len(token_end_offsets)
    ):
        return text[token_start_offsets[start] : token_end_offsets[stop - 1]]
    return render_tokens(row["tokens"][start:stop], row.get("token_render", [])[start:stop])


def entity_record(entity: Entity | None, row: dict[str, Any]) -> dict[str, Any] | None:
    if entity is None:
        return None
    start, stop, label = entity
    token_start_offsets = row.get("token_start_offsets", [])
    token_end_offsets = row.get("token_end_offsets", [])
    char_start = token_start_offsets[start] if start < len(token_start_offsets) else None
    char_stop = token_end_offsets[stop - 1] if stop - 1 < len(token_end_offsets) else None
    return {
        "label": label,
        "token_start": start,
        "token_stop": stop,
        "surface": natural_text(row, start, stop),
        "char_start": char_start,
        "char_stop": char_stop,
    }


def overlap(left: Entity, right: Entity) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def overlap_components(gold_entities: set[Entity], pred_entities: set[Entity]) -> list[tuple[list[Entity], list[Entity]]]:
    remaining_gold = set(gold_entities)
    remaining_pred = set(pred_entities)
    components: list[tuple[list[Entity], list[Entity]]] = []
    while remaining_gold or remaining_pred:
        if remaining_gold:
            component_gold = {min(remaining_gold)}
            component_pred: set[Entity] = set()
        else:
            component_gold = set()
            component_pred = {min(remaining_pred)}
        changed = True
        while changed:
            changed = False
            for pred in list(remaining_pred - component_pred):
                if any(overlap(gold, pred) for gold in component_gold):
                    component_pred.add(pred)
                    changed = True
            for gold in list(remaining_gold - component_gold):
                if any(overlap(gold, pred) for pred in component_pred):
                    component_gold.add(gold)
                    changed = True
        remaining_gold -= component_gold
        remaining_pred -= component_pred
        components.append((sorted(component_gold), sorted(component_pred)))
    return sorted(
        components,
        key=lambda component: min([entity[0] for entity in [*component[0], *component[1]]]),
    )


def alignment_outcome(gold: list[Entity], predictions: list[Entity]) -> str:
    if not gold:
        return "extra"
    if not predictions:
        return "missed"
    if len(gold) == len(predictions) == 1:
        gold_entity = gold[0]
        pred_entity = predictions[0]
        same_span = gold_entity[:2] == pred_entity[:2]
        same_label = gold_entity[2] == pred_entity[2]
        if same_span and same_label:
            return "correct"
        if same_span:
            return "wrong_label"
        if same_label:
            return "span_mismatch"
        return "wrong_label_and_span"
    return "complex_overlap"


def align_entities(gold_entities: set[Entity], pred_entities: set[Entity]) -> list[EntityAlignment]:
    alignments = [
        EntityAlignment("correct", (entity,), (entity,))
        for entity in sorted(gold_entities & pred_entities)
    ]
    remaining_gold = gold_entities - (gold_entities & pred_entities)
    remaining_pred = pred_entities - (gold_entities & pred_entities)
    for gold, predictions in overlap_components(remaining_gold, remaining_pred):
        alignments.append(
            EntityAlignment(
                alignment_outcome(gold, predictions),
                tuple(gold),
                tuple(predictions),
            )
        )
    return sorted(
        alignments,
        key=lambda item: min([entity[0] for entity in [*item.gold, *item.predictions]] or [0]),
    )
