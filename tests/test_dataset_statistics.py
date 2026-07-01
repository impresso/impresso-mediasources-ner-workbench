from lib.dataset_statistics import collect_statistics, render_markdown


def row(document_id: str, language: str, label: str | None, *, newspaper: str, date: str) -> dict:
    entities = [] if label is None else [{"label": label, "token_start": 0, "token_stop": 1}]
    return {
        "document_id": document_id,
        "language": language,
        "newspaper": newspaper,
        "date": date,
        "tokens": ["Radio", "reports"],
        "entities": entities,
    }


def test_dataset_statistics_render_release_markdown() -> None:
    rows = {
        "train": [row("doc-1", "de", "org.ent.pressagency.wolff", newspaper="FZG", date="1931-02-26")],
        "validation": [row("doc-2", "fr", "org.ent.radiostation.bbc", newspaper="JDG", date="1952-01-11")],
        "test": [row("doc-1", "de", None, newspaper="FZG", date="1931-02-26")],
    }

    stats = collect_statistics(rows)
    report = render_markdown(stats, release="v2.0.0")

    assert stats["splits"]["train"]["tokens"] == 2
    assert stats["duplicate_document_ids"] == {"doc-1": ["test", "train"]}
    assert stats["families"]["validation"] == {"radio station": 1}
    assert "# Dataset Statistics: v2.0.0" in report
    assert "| `org.ent.pressagency.wolff` | 1 | 0 | 0 | 1 |" in report
    assert "Warning: 1 document IDs occur in more than one split." in report
