import json

from lib.tsv_hit_pager import RED, RESET, build_block, document_id_for_hit, filter_audited_hits, find_hits, highlight_token_line, hit_label_for_hit, hit_title, is_token_line, parse_token_line


def test_tsv_hit_pager_identifies_token_lines() -> None:
    assert not is_token_line("")
    assert not is_token_line("# document_id = doc-1\n")
    assert not is_token_line("TOKEN\tNERTAG\n")
    assert is_token_line("BBC\tO\n")
    assert parse_token_line("BBC\tB-org.ent.radiostation.bbc\n") == ("BBC", "B-org.ent.radiostation.bbc")


def test_tsv_hit_pager_finds_single_token_case_insensitive() -> None:
    lines = ["# document_id = doc-1\n", "TOKEN\tNERTAG\n", "bbc\tO\n", "BBC\tB-x\n"]

    assert find_hits(lines, "BBC") == [(2, 3), (3, 4)]
    assert find_hits(lines, "BBC", ignore_case=False) == [(3, 4)]


def test_tsv_hit_pager_finds_adjacent_two_token_hits() -> None:
    lines = ["Radio\tO\n", "London\tO\n", "\n", "Radio\tO\n", "# comment\n", "London\tO\n"]

    assert find_hits(lines, "radio", "london") == [(0, 2)]


def test_tsv_hit_pager_only_o_requires_o_tags() -> None:
    lines = ["Radio\tO\n", "London\tB-org.ent.radiostation.bbc\n", "Radio\tO\n", "London\tO\n"]

    assert find_hits(lines, "Radio", "London") == [(0, 2), (2, 4)]
    assert find_hits(lines, "Radio", "London", only_o=True) == [(2, 4)]


def test_tsv_hit_pager_builds_context_block_with_highlight() -> None:
    lines = ["before\tO\n", "BBC\tO\n", "after\tO\n"]

    block = build_block(lines, (1, 2), context=1, query_tokens=["bbc"])

    assert "before\tO" in block
    assert f"{RED}BBC{RESET}\tO" in block
    assert "after\tO" in block


def test_tsv_hit_pager_context_does_not_cross_into_next_document() -> None:
    lines = [
        "# doc_id = doc-1\n",
        "TOKEN\tNERTAG\n",
        "die\tO\n",
        "BBC\tO\n",
        "# doc_id = doc-2\n",
        "TOKEN\tNERTAG\n",
        "BBC\tO\n",
    ]

    block = build_block(lines, (3, 4), context=10, query_tokens=["bbc"], color=False)

    assert "die\tO" in block
    assert "BBC\tO" in block
    assert "doc-2" not in block


def test_tsv_hit_pager_context_does_not_cross_from_previous_document() -> None:
    lines = [
        "# doc_id = doc-1\n",
        "TOKEN\tNERTAG\n",
        "BBC\tO\n",
        "\n",
        "# doc_id = doc-2\n",
        "TOKEN\tNERTAG\n",
        "BBC\tO\n",
        "after\tO\n",
    ]

    block = build_block(lines, (6, 7), context=10, query_tokens=["bbc"], color=False)

    assert "doc-1" not in block
    assert block.startswith("# doc_id = doc-2\n")
    assert "after\tO" in block


def test_tsv_hit_pager_extracts_document_id_for_hit_title() -> None:
    lines = [
        "# doc_id = row-id\n",
        "# document_id = DTT-1953-08-23-a-i0006\n",
        "# split = train\n",
        "TOKEN\tNERTAG\n",
        "BBC\tO\n",
    ]

    assert document_id_for_hit(lines, (4, 5)) == "DTT-1953-08-23-a-i0006"
    assert hit_label_for_hit(lines, (4, 5)) == "DTT-1953-08-23-a-i0006 [train]"
    assert hit_title(1, 7, hit_label_for_hit(lines, (4, 5))) == "Hit 1/7 DTT-1953-08-23-a-i0006 [train]"


def test_tsv_hit_pager_can_disable_highlight_color() -> None:
    assert highlight_token_line("BBC\tO\n", ["bbc"], color=False) == "BBC\tO\n"


def test_tsv_hit_pager_filters_verified_audit_marks(tmp_path) -> None:
    source = tmp_path / "train.jsonl"
    source.write_text(
        json.dumps(
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "tokens": ["Die", "BBC"],
                "token_start_offsets": [0, 4],
                "token_end_offsets": [3, 7],
                "audit_marks": [{"audit_id": "manual-tsv-train", "decision": "accept", "label": "O", "start": 4, "status": "verified", "stop": 7}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    lines = ["# doc_id = doc-1\n", "# document_id = doc-1\n", "TOKEN\tNERTAG\n", "Die\tO\n", "BBC\tO\n"]
    hits = find_hits(lines, "BBC")

    assert filter_audited_hits(lines, hits, source_jsonl=source, include_audited=False) == []
    assert filter_audited_hits(lines, hits, source_jsonl=source, include_audited=True) == hits
