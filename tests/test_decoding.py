from __future__ import annotations

import math
import random
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINING_SRC = ROOT / "training" / "newsagency-radiostation-modernbert-classifier" / "src"
sys.path.insert(0, str(TRAINING_SRC))

from mediaagency_modernbert.decoding import (  # noqa: E402
    DECODER_ALL_SUBTOKEN,
    DECODER_ALL_SUBTOKEN_VITERBI,
    DECODER_FIRST_SUBTOKEN,
    DECODER_FIRST_SUBTOKEN_VITERBI,
    NEG_INF,
    all_subtoken_emissions,
    compile_bio_schema,
    decode_bio_viterbi_reference,
    decode_document,
    semantic_label_margin,
    semantic_label_probability,
    start_score,
    transition_score,
    viterbi_decode,
)


ID2LABEL = {
    0: "O",
    1: "B-X",
    2: "I-X",
    3: "B-Y",
    4: "I-Y",
}
LABEL2ID = {label: index for index, label in ID2LABEL.items()}
NONSTANDARD_ID2LABEL = {
    0: "O",
    1: "I-X",
    2: "B-X",
    3: "I-Y",
    4: "B-Y",
}


def log_probs(values: list[float]) -> list[float]:
    return [math.log(value) for value in values]


def test_viterbi_transition_grammar() -> None:
    assert start_score("O") == 0.0
    assert start_score("B-X") == 0.0
    assert start_score("I-X") == NEG_INF
    assert transition_score("O", "I-X") == NEG_INF
    assert transition_score("B-Y", "I-X") == NEG_INF
    assert transition_score("I-Y", "I-X") == NEG_INF
    assert transition_score("B-X", "I-X") == 0.0
    assert transition_score("I-X", "I-X") == 0.0
    assert transition_score("B-X", "B-X") == NEG_INF
    assert transition_score("I-X", "B-X") == NEG_INF
    assert transition_score("B-X", "B-Y") == 0.0
    assert transition_score("B-X", "O") == 0.0


def test_same_type_contact_rule_is_project_specific() -> None:
    emissions = [
        [0.0, 10.0, 0.0, -5.0, -5.0],
        [0.0, 10.0, 9.0, -5.0, -5.0],
    ]

    pred = viterbi_decode(emissions, ID2LABEL)

    assert [ID2LABEL[index] for index in pred] == ["B-X", "I-X"]


def test_compile_bio_schema_validates_label_topology() -> None:
    schema = compile_bio_schema(ID2LABEL)

    assert schema.label_count == 5
    assert schema.o_id == 0
    assert schema.entity_names == ("X", "Y")
    assert schema.b_ids == (1, 3)
    assert schema.i_ids == (2, 4)

    try:
        compile_bio_schema({0: "O", 1: "B-X"})
    except ValueError as exc:
        assert "requires I labels" in str(exc)
    else:
        raise AssertionError("expected missing I label error")


def test_all_subtoken_emissions_use_b_then_i_word_expansion() -> None:
    word_subtokens = [
        [
            log_probs([0.01, 0.70, 0.10, 0.10, 0.09]),
            log_probs([0.01, 0.05, 0.80, 0.05, 0.09]),
        ]
    ]

    emissions = all_subtoken_emissions(word_subtokens, compile_bio_schema(ID2LABEL))

    assert emissions[0][LABEL2ID["O"]] == math.log(0.01) + math.log(0.01)
    assert emissions[0][LABEL2ID["B-X"]] == math.log(0.70) + math.log(0.80)
    assert emissions[0][LABEL2ID["I-X"]] == math.log(0.10) + math.log(0.80)


def test_first_subtoken_decoder_preserves_raw_argmax() -> None:
    word_subtokens = [[log_probs([0.05, 0.10, 0.80, 0.03, 0.02])]]

    pred = decode_document(word_subtokens, decoder=DECODER_FIRST_SUBTOKEN, id2label=ID2LABEL)

    assert [ID2LABEL[index] for index in pred] == ["I-X"]


def test_first_subtoken_viterbi_repairs_illegal_initial_inside_tag() -> None:
    word_subtokens = [[log_probs([0.05, 0.10, 0.80, 0.03, 0.02])]]

    pred = decode_document(word_subtokens, decoder=DECODER_FIRST_SUBTOKEN_VITERBI, id2label=ID2LABEL)

    assert [ID2LABEL[index] for index in pred] == ["B-X"]


def test_first_subtoken_viterbi_merges_same_entity_in_contact() -> None:
    word_subtokens = [
        [log_probs([0.01, 0.90, 0.05, 0.02, 0.02])],
        [log_probs([0.01, 0.70, 0.20, 0.05, 0.04])],
    ]

    pred = decode_document(word_subtokens, decoder=DECODER_FIRST_SUBTOKEN_VITERBI, id2label=ID2LABEL)

    assert [ID2LABEL[index] for index in pred] == ["B-X", "I-X"]


def test_optimized_viterbi_matches_reference_decoder() -> None:
    rng = random.Random(42)
    for length in range(1, 9):
        for _case in range(100):
            emissions = [[rng.uniform(-5.0, 1.0) for _label in ID2LABEL] for _position in range(length)]

            reference = decode_bio_viterbi_reference(emissions, ID2LABEL)
            optimized = viterbi_decode(emissions, ID2LABEL)

            assert optimized == reference


def test_optimized_viterbi_matches_reference_decoder_on_ties() -> None:
    tied_cases = [
        [[0.0, 0.0, 0.0, 0.0, 0.0]],
        [[0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0]],
        [[-1.0, 0.0, 0.0, 0.0, 0.0], [-1.0, 0.0, 0.0, 0.0, 0.0]],
        [[0.0, 5.0, 4.0, 5.0, 4.0], [0.0, 5.0, 5.0, 5.0, 5.0]],
        [[NEG_INF, NEG_INF, NEG_INF, NEG_INF, NEG_INF], [0.0, 0.0, 0.0, 0.0, 0.0]],
        [[0.0, NEG_INF, NEG_INF, NEG_INF, NEG_INF], [NEG_INF, NEG_INF, NEG_INF, NEG_INF, NEG_INF]],
    ]

    for emissions in tied_cases:
        assert viterbi_decode(emissions, ID2LABEL) == decode_bio_viterbi_reference(emissions, ID2LABEL)


def test_optimized_viterbi_matches_reference_decoder_with_random_negative_infinity() -> None:
    rng = random.Random(123)
    for length in range(1, 9):
        for _case in range(100):
            emissions = []
            for _position in range(length):
                row = []
                for _label in ID2LABEL:
                    row.append(NEG_INF if rng.random() < 0.2 else rng.uniform(-5.0, 1.0))
                emissions.append(row)

            assert viterbi_decode(emissions, ID2LABEL) == decode_bio_viterbi_reference(emissions, ID2LABEL)


def test_optimized_viterbi_matches_reference_with_nonstandard_b_i_ordering() -> None:
    rng = random.Random(456)
    tied_cases = [
        [[0.0, 0.0, 0.0, 0.0, 0.0]],
        [[0.0, 5.0, 5.0, 0.0, 0.0], [0.0, 5.0, 5.0, 0.0, 0.0]],
        [[NEG_INF, NEG_INF, NEG_INF, NEG_INF, NEG_INF], [0.0, 0.0, 0.0, 0.0, 0.0]],
    ]
    for emissions in tied_cases:
        assert viterbi_decode(emissions, NONSTANDARD_ID2LABEL) == decode_bio_viterbi_reference(emissions, NONSTANDARD_ID2LABEL)

    for length in range(1, 9):
        for _case in range(100):
            emissions = []
            for _position in range(length):
                row = []
                for _label in NONSTANDARD_ID2LABEL:
                    row.append(NEG_INF if rng.random() < 0.2 else rng.choice([0.0, rng.uniform(-5.0, 1.0)]))
                emissions.append(row)

            assert viterbi_decode(emissions, NONSTANDARD_ID2LABEL) == decode_bio_viterbi_reference(emissions, NONSTANDARD_ID2LABEL)


def test_all_subtoken_viterbi_uses_continuation_evidence() -> None:
    word_subtokens = [
        [
            log_probs([0.51, 0.47, 0.01, 0.005, 0.005]),
            log_probs([0.02, 0.005, 0.96, 0.005, 0.01]),
        ]
    ]

    first = decode_document(word_subtokens, decoder=DECODER_FIRST_SUBTOKEN, id2label=ID2LABEL)
    all_subtokens = decode_document(word_subtokens, decoder=DECODER_ALL_SUBTOKEN_VITERBI, id2label=ID2LABEL)

    assert [ID2LABEL[index] for index in first] == ["O"]
    assert [ID2LABEL[index] for index in all_subtokens] == ["B-X"]


def test_all_subtoken_argmax_uses_continuation_evidence_without_sequence_constraints() -> None:
    word_subtokens = [
        [
            log_probs([0.51, 0.47, 0.01, 0.005, 0.005]),
            log_probs([0.02, 0.005, 0.96, 0.005, 0.01]),
        ]
    ]

    pred = decode_document(word_subtokens, decoder=DECODER_ALL_SUBTOKEN, id2label=ID2LABEL)

    assert [ID2LABEL[index] for index in pred] == ["B-X"]


def test_all_subtoken_argmax_can_emit_bio_invalid_sequence() -> None:
    word_subtokens = [
        [log_probs([0.05, 0.10, 0.80, 0.03, 0.02])],
    ]

    pred = decode_document(word_subtokens, decoder=DECODER_ALL_SUBTOKEN, id2label=ID2LABEL)

    assert [ID2LABEL[index] for index in pred] == ["I-X"]


def test_all_subtoken_viterbi_keeps_strong_outside_evidence() -> None:
    word_subtokens = [
        [
            log_probs([0.90, 0.05, 0.02, 0.02, 0.01]),
            log_probs([0.88, 0.02, 0.05, 0.03, 0.02]),
        ]
    ]

    pred = decode_document(word_subtokens, decoder=DECODER_ALL_SUBTOKEN_VITERBI, id2label=ID2LABEL)

    assert [ID2LABEL[index] for index in pred] == ["O"]


def test_semantic_label_probability_uses_entity_type_not_bio_position() -> None:
    schema = compile_bio_schema(ID2LABEL)
    probabilities = [0.20, 0.10, 0.60, 0.05, 0.05]

    confidence = semantic_label_probability(log_probs(probabilities), LABEL2ID["B-X"], schema)
    margin = semantic_label_margin(log_probs(probabilities), LABEL2ID["B-X"], schema)

    assert math.isclose(confidence, 0.70)
    assert math.isclose(margin, 0.50)


def test_semantic_label_probability_for_outside_uses_o_probability() -> None:
    schema = compile_bio_schema(ID2LABEL)
    probabilities = [0.72, 0.10, 0.08, 0.05, 0.05]

    assert math.isclose(semantic_label_probability(log_probs(probabilities), LABEL2ID["O"], schema), 0.72)


def test_hf_model_decoder_matches_training_decoder_source() -> None:
    training_decoder = TRAINING_SRC / "mediaagency_modernbert" / "decoding.py"
    hf_decoder = ROOT / "hf_model" / "decoding.py"

    assert hf_decoder.read_text() == training_decoder.read_text()
