from __future__ import annotations

import pytest

from lib.sync_label_map import make_label_map


def test_label_map_adds_bio_pair_for_single_token_entity_label() -> None:
    label_map = make_label_map(
        [{"token_labels": ["O", "B-org.ent.pressagency.keystone", "O"]}]
    )

    assert set(label_map["label2id"]) == {
        "O",
        "B-org.ent.pressagency.keystone",
        "I-org.ent.pressagency.keystone",
    }


def test_label_map_adds_bio_pairs_for_metadata_only_entity_labels() -> None:
    label_map = make_label_map(
        [{"token_labels": ["O"]}],
        extra_entity_labels={"org.ent.pressagency.belga"},
    )

    assert set(label_map["label2id"]) == {
        "O",
        "B-org.ent.pressagency.belga",
        "I-org.ent.pressagency.belga",
    }


def test_label_map_rejects_non_bio_entity_labels() -> None:
    with pytest.raises(ValueError, match="must use BIO prefixes"):
        make_label_map([{"token_labels": ["org.ent.pressagency.keystone"]}])
