from types import SimpleNamespace

import pytest

from mediaagency_modernbert.train import git_provenance, label_compatibility_summary, label_map_from_model_config


def test_label_map_from_model_config_preserves_checkpoint_head_labels() -> None:
    config = SimpleNamespace(
        num_labels=3,
        id2label={
            0: "O",
            1: "B-org.ent.pressagency.wolff",
            2: "I-org.ent.pressagency.wolff",
        },
        label2id={
            "O": 0,
            "B-org.ent.pressagency.wolff": 1,
            "I-org.ent.pressagency.wolff": 2,
        },
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


def test_label_map_from_model_config_rejects_incomplete_bio_pairs() -> None:
    config = SimpleNamespace(
        num_labels=2,
        id2label={0: "O", 1: "B-org.ent.pressagency.belga"},
        label2id={"O": 0, "B-org.ent.pressagency.belga": 1},
    )

    with pytest.raises(ValueError, match="requires I labels"):
        label_map_from_model_config(config)


def test_label_map_from_model_config_rejects_non_inverse_label_maps() -> None:
    config = SimpleNamespace(
        num_labels=3,
        id2label={
            0: "O",
            1: "B-org.ent.pressagency.wolff",
            2: "I-org.ent.pressagency.wolff",
        },
        label2id={
            "O": 0,
            "B-org.ent.pressagency.wolff": 2,
            "I-org.ent.pressagency.wolff": 1,
        },
    )

    with pytest.raises(ValueError, match="exact inverses"):
        label_map_from_model_config(config)


def test_label_compatibility_summary_reports_dataset_and_checkpoint_drift() -> None:
    dataset_label_map = {
        "label2id": {
            "O": 0,
            "B-org.ent.pressagency.wolff": 1,
            "I-org.ent.pressagency.wolff": 2,
            "B-org.ent.pressagency.belga": 3,
            "I-org.ent.pressagency.belga": 4,
        }
    }
    checkpoint_label_map = {
        "label2id": {
            "O": 0,
            "B-org.ent.pressagency.wolff": 7,
            "I-org.ent.pressagency.wolff": 8,
            "B-org.ent.pressagency.domei": 9,
            "I-org.ent.pressagency.domei": 10,
        }
    }

    summary = label_compatibility_summary(dataset_label_map, checkpoint_label_map)

    assert summary["shared_labels"] == 3
    assert summary["dataset_only_entity_types"] == ["org.ent.pressagency.belga"]
    assert summary["checkpoint_only_entity_types"] == ["org.ent.pressagency.domei"]


def test_git_provenance_reports_clean_commit(monkeypatch) -> None:
    def fake_run(args, **_kwargs):
        command = tuple(args[1:])
        if command == ("rev-parse", "HEAD"):
            return SimpleNamespace(stdout="a" * 40 + "\n")
        if command == ("rev-parse", "--short", "HEAD"):
            return SimpleNamespace(stdout="aaaaaaa\n")
        if command == ("status", "--short"):
            return SimpleNamespace(stdout="")
        raise AssertionError(command)

    monkeypatch.setattr("mediaagency_modernbert.train.subprocess.run", fake_run)

    assert git_provenance() == {
        "commit": "a" * 40,
        "dirty": False,
        "short_commit": "aaaaaaa",
        "status": "clean",
    }


def test_git_provenance_reports_dirty_commit(monkeypatch) -> None:
    def fake_run(args, **_kwargs):
        command = tuple(args[1:])
        if command == ("rev-parse", "HEAD"):
            return SimpleNamespace(stdout="b" * 40 + "\n")
        if command == ("rev-parse", "--short", "HEAD"):
            return SimpleNamespace(stdout="bbbbbbb\n")
        if command == ("status", "--short"):
            return SimpleNamespace(stdout=" M Makefile\n")
        raise AssertionError(command)

    monkeypatch.setattr("mediaagency_modernbert.train.subprocess.run", fake_run)

    assert git_provenance()["status"] == "dirty"
    assert git_provenance()["dirty"] is True


def test_git_provenance_is_best_effort(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        raise OSError("git unavailable")

    monkeypatch.setattr("mediaagency_modernbert.train.subprocess.run", fake_run)

    assert git_provenance() == {
        "commit": None,
        "dirty": None,
        "short_commit": None,
        "status": "unknown",
    }
