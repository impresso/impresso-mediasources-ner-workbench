from pathlib import Path

from lib.curation_article_ids import collect_article_ids, row_document_id
from lib.snippet_data import write_jsonl


def test_row_document_id_reads_dataset_and_snippet_shapes() -> None:
    assert row_document_id({"document_id": "NZZ-1794-08-09-a-i0002#fragment"}) == "NZZ-1794-08-09-a-i0002"
    assert row_document_id({"sample_document_id": "GDL-1975-04-18-a-i0119"}) == "GDL-1975-04-18-a-i0119"
    assert row_document_id({"source": {"document_id": "DP-1975-10-30-a-i0007"}}) == "DP-1975-10-30-a-i0007"
    assert row_document_id({"id": "cookbook-snippet:BBLT-1877-02-23-a-i0106"}) == "BBLT-1877-02-23-a-i0106"


def test_collect_article_ids_deduplicates_and_records_sources(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    reviewed = tmp_path / "reviewed.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    write_jsonl(
        train,
        [
            {"document_id": "NZZ-1794-08-09-a-i0002"},
            {"document_id": "DP-1975-10-30-a-i0007"},
        ],
    )
    write_jsonl(
        reviewed,
        [
            {"sample_document_id": "NZZ-1794-08-09-a-i0002"},
            {"source": {"document_id": "GDL-1975-04-18-a-i0119"}},
        ],
    )
    write_jsonl(candidates, [{"id": "cookbook-snippet:BBLT-1877-02-23-a-i0106"}])

    rows = collect_article_ids(
        [
            ("dataset-train", train),
            ("newsagency-reviewed", reviewed),
            ("newsagency-candidates", candidates),
        ]
    )

    assert [row["content_item_id"] for row in rows] == [
        "BBLT-1877-02-23-a-i0106",
        "DP-1975-10-30-a-i0007",
        "GDL-1975-04-18-a-i0119",
        "NZZ-1794-08-09-a-i0002",
    ]
    nzz = rows[-1]
    assert nzz["sources"] == [
        {"path": str(train), "role": "dataset-train"},
        {"path": str(reviewed), "role": "newsagency-reviewed"},
    ]
