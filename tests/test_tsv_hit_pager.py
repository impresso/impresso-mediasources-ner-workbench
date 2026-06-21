from lib.tsv_hit_pager import RED, RESET, build_block, find_hits, highlight_token_line, is_token_line, parse_token_line


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


def test_tsv_hit_pager_can_disable_highlight_color() -> None:
    assert highlight_token_line("BBC\tO\n", ["bbc"], color=False) == "BBC\tO\n"
