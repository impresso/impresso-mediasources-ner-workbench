from lib.entity_alignment import align_entities, labels_to_entities


def outcomes(gold_labels: list[str], pred_labels: list[str]) -> list[str]:
    gold = labels_to_entities(gold_labels)
    pred = labels_to_entities(pred_labels, merge_adjacent_same_label=True)
    return [alignment.outcome for alignment in align_entities(gold, pred)]


def test_align_entities_classifies_exact_match() -> None:
    label = "org.ent.pressagency.apa"

    assert outcomes([f"B-{label}"], [f"B-{label}"]) == ["correct"]


def test_align_entities_classifies_wrong_label_same_span() -> None:
    assert outcomes(
        ["B-org.ent.pressagency.apa"],
        ["B-org.ent.pressagency.afp"],
    ) == ["wrong_label"]


def test_align_entities_classifies_span_mismatch_same_label() -> None:
    label = "org.ent.pressagency.afp"

    assert outcomes(
        [f"B-{label}", f"I-{label}"],
        ["O", f"B-{label}"],
    ) == ["span_mismatch"]


def test_align_entities_classifies_missed_and_extra() -> None:
    assert outcomes(
        ["B-org.ent.pressagency.afp", "O", "O"],
        ["O", "O", "B-org.ent.pressagency.havas"],
    ) == ["missed", "extra"]


def test_align_entities_preserves_complex_overlap() -> None:
    assert outcomes(
        ["B-org.ent.pressagency.ctk", "I-org.ent.pressagency.ctk"],
        ["B-org.ent.pressagency.ctk", "B-org.ent.pressagency.ctk"],
    ) == ["correct"]

    assert outcomes(
        ["B-org.ent.pressagency.ctk", "I-org.ent.pressagency.ctk"],
        ["B-org.ent.pressagency.reuters", "B-org.ent.pressagency.ctk"],
    ) == ["complex_overlap"]
