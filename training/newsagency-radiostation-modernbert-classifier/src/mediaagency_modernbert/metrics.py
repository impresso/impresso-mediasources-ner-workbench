from __future__ import annotations

from collections import Counter

from .data import labels_to_entities


def token_metrics(gold: list[str], pred: list[str]) -> dict[str, float | int]:
    if len(gold) != len(pred):
        raise ValueError("gold and pred label lists must have equal length")
    labels = sorted({label for label in gold + pred if label != "O"})
    correct = sum(1 for g, p in zip(gold, pred, strict=True) if g == p)
    total = len(gold)
    non_o_gold = sum(1 for g in gold if g != "O")
    non_o_pred = sum(1 for p in pred if p != "O")
    non_o_correct = sum(1 for g, p in zip(gold, pred, strict=True) if g == p and g != "O")
    precision = safe_div(non_o_correct, non_o_pred)
    recall = safe_div(non_o_correct, non_o_gold)
    return {
        "token_accuracy": safe_div(correct, total),
        "token_non_o_precision": precision,
        "token_non_o_recall": recall,
        "token_non_o_f1": f1(precision, recall),
        "token_total": total,
        "token_non_o_gold": non_o_gold,
        "token_non_o_pred": non_o_pred,
        "token_label_count": len(labels),
    }


def entity_metrics(gold_labels_by_doc: dict[str, list[str]], pred_labels_by_doc: dict[str, list[str]]) -> dict[str, float | int]:
    gold_entities = set()
    pred_entities = set()
    for doc_id, labels in gold_labels_by_doc.items():
        for start, stop, label in labels_to_entities(labels):
            gold_entities.add((doc_id, start, stop, label))
    for doc_id, labels in pred_labels_by_doc.items():
        for start, stop, label in labels_to_entities(labels):
            pred_entities.add((doc_id, start, stop, label))
    correct = len(gold_entities & pred_entities)
    precision = safe_div(correct, len(pred_entities))
    recall = safe_div(correct, len(gold_entities))
    return {
        "entity_precision": precision,
        "entity_recall": recall,
        "entity_f1": f1(precision, recall),
        "entity_gold": len(gold_entities),
        "entity_pred": len(pred_entities),
        "entity_correct": correct,
    }


def entity_metrics_by_label(gold_labels_by_doc: dict[str, list[str]], pred_labels_by_doc: dict[str, list[str]]) -> dict[str, dict[str, float | int]]:
    gold = Counter()
    pred = Counter()
    correct = Counter()
    gold_entities = {}
    pred_entities = {}
    for doc_id, labels in gold_labels_by_doc.items():
        for start, stop, label in labels_to_entities(labels):
            key = (doc_id, start, stop, label)
            gold_entities[key] = label
            gold[label] += 1
    for doc_id, labels in pred_labels_by_doc.items():
        for start, stop, label in labels_to_entities(labels):
            key = (doc_id, start, stop, label)
            pred_entities[key] = label
            pred[label] += 1
    for key, label in gold_entities.items():
        if key in pred_entities:
            correct[label] += 1
    out = {}
    for label in sorted(set(gold) | set(pred)):
        precision = safe_div(correct[label], pred[label])
        recall = safe_div(correct[label], gold[label])
        out[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1(precision, recall),
            "gold": gold[label],
            "pred": pred[label],
            "correct": correct[label],
        }
    return out


def safe_div(num: int | float, den: int | float) -> float:
    return float(num) / float(den) if den else 0.0


def f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0
