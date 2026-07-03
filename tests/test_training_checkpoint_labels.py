from types import SimpleNamespace

from mediaagency_modernbert.train import label_map_from_model_config


def test_label_map_from_model_config_preserves_checkpoint_head_labels() -> None:
    config = SimpleNamespace(
        id2label={
            0: "O",
            1: "B-org.ent.pressagency.wolff",
            2: "I-org.ent.pressagency.wolff",
        }
    )

    assert label_map_from_model_config(config) == {
        "id2label": {
            "0": "O",
            "1": "B-org.ent.pressagency.wolff",
            "2": "I-org.ent.pressagency.wolff",
        },
        "label2id": {
            "O": 0,
            "B-org.ent.pressagency.wolff": 1,
            "I-org.ent.pressagency.wolff": 2,
        },
    }
