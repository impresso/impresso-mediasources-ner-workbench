import json
from pathlib import Path

from lib.apply_span_patch_decisions import apply_span_patches, labels_from_entities
import pytest
import lib.create_span_patches_from_tsv as tsv_patches

from lib.create_span_patches_from_tsv import (
    ActionableTarget,
    PatchTarget,
    actionable_target_pairs,
    build_accepted_patches,
    find_token_matches,
    match_context,
    parse_match_selection,
    parse_tsv_paste,
    resolve_label,
    split_pasted_blocks,
    target_from_new_labels,
    targets_from_new_labels,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_main_loop_reads_multiple_pasted_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    blocks: list[str] = []

    def fake_process(args, pasted_tsv, label_metadata):
        blocks.append(pasted_tsv)
        return 0

    inputs = iter(["A O", "", "y", "B O", "", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(tsv_patches, "stdin_has_buffered_line", lambda: False)
    monkeypatch.setattr(tsv_patches, "process_pasted_tsv", fake_process)

    result = tsv_patches.main(
        [
            "--input-jsonl",
            str(tmp_path / "input.jsonl"),
            "--candidates",
            str(tmp_path / "candidates.jsonl"),
            "--decisions",
            str(tmp_path / "decisions.jsonl"),
            "--audit-id",
            "manual-tsv-test",
            "--reviewer",
            "tester",
            "--loop",
        ]
    )

    assert result == 0
    assert blocks == ["A O", "B O"]


def test_main_loop_processes_blank_separated_patches_from_one_paste(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    blocks: list[str] = []

    def fake_process(args, pasted_tsv, label_metadata):
        blocks.append(pasted_tsv)
        return 0

    inputs = iter(["A O", "", "B O", "", "n"])
    buffered = iter([True, False])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(tsv_patches, "stdin_has_buffered_line", lambda: next(buffered))
    monkeypatch.setattr(tsv_patches, "process_pasted_tsv", fake_process)

    result = tsv_patches.main(
        [
            "--input-jsonl",
            str(tmp_path / "input.jsonl"),
            "--candidates",
            str(tmp_path / "candidates.jsonl"),
            "--decisions",
            str(tmp_path / "decisions.jsonl"),
            "--audit-id",
            "manual-tsv-test",
            "--reviewer",
            "tester",
            "--loop",
        ]
    )

    assert result == 0
    assert blocks == ["A O", "B O"]


def test_main_without_loop_reads_one_pasted_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    blocks: list[str] = []

    def fake_process(args, pasted_tsv, label_metadata):
        blocks.append(pasted_tsv)
        return 0

    inputs = iter(["A O", "", "B O", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(tsv_patches, "process_pasted_tsv", fake_process)

    result = tsv_patches.main(
        [
            "--input-jsonl",
            str(tmp_path / "input.jsonl"),
            "--candidates",
            str(tmp_path / "candidates.jsonl"),
            "--decisions",
            str(tmp_path / "decisions.jsonl"),
            "--audit-id",
            "manual-tsv-test",
            "--reviewer",
            "tester",
        ]
    )

    assert result == 0
    assert blocks == ["A O"]


def test_split_pasted_blocks_uses_one_or_more_empty_lines_as_segment_separator() -> None:
    assert split_pasted_blocks("A\tO\n\n\nB\tO\n\nC\tO\n") == ["A\tO", "B\tO", "C\tO"]


def test_parse_tsv_paste_reads_comments_and_token_column() -> None:
    sequence = parse_tsv_paste(
        "# document_id = doc-1\n"
        "TOKEN\tNERTAG\n"
        "Agence\tO\n"
        "Havas\tO\n"
    )

    assert sequence.metadata["document_id"] == "doc-1"
    assert sequence.tokens == ("Agence", "Havas")


def test_parse_tsv_paste_accepts_whitespace_separated_columns() -> None:
    sequence = parse_tsv_paste("Deutsche        O\nWelle   O\n")

    assert sequence.tokens == ("Deutsche", "Welle")


def test_parse_tsv_paste_reads_old_new_columns() -> None:
    sequence = parse_tsv_paste(
        "TOKEN\tOLD\tNEW\n"
        "encore\tB-org.ent.radiostation.deutsche-welle\tO\n"
        "longtemps\tI-org.ent.radiostation.deutsche-welle\tO\n"
    )

    assert sequence.tokens == ("encore", "longtemps")
    assert sequence.old_labels == (
        "B-org.ent.radiostation.deutsche-welle",
        "I-org.ent.radiostation.deutsche-welle",
    )
    assert sequence.new_labels == ("O", "O")


def test_parse_tsv_paste_rejects_partial_old_label_columns() -> None:
    with pytest.raises(ValueError, match="OLD/NERTAG label for every token row"):
        parse_tsv_paste("Agence\tB-org.ent.pressagency.havas\nHavas\n")


def test_parse_tsv_paste_accepts_mixed_tabs_and_spaces_between_columns() -> None:
    sequence = parse_tsv_paste(
        "Die\tO       O\n"
        "Agence\tB-org.ent.pressagency.havas     O\n"
        "Haoas\tI-org.ent.pressagency.havas      B-org.ent.pressagency.havas\n"
    )

    assert sequence.tokens == ("Die", "Agence", "Haoas")
    assert sequence.old_labels == (
        "O",
        "B-org.ent.pressagency.havas",
        "I-org.ent.pressagency.havas",
    )
    assert sequence.new_labels == (
        "O",
        "O",
        "B-org.ent.pressagency.havas",
    )


def test_parse_tsv_paste_normalizes_lowercase_o_and_dash_outside_labels() -> None:
    sequence = parse_tsv_paste(
        "Die\to\t-\n"
        "Agence\tB-org.ent.pressagency.havas\to\n"
        "Haoas\tI-org.ent.pressagency.havas\tB-org.ent.pressagency.havas\n"
    )

    assert sequence.old_labels == (
        "O",
        "B-org.ent.pressagency.havas",
        "I-org.ent.pressagency.havas",
    )
    assert sequence.new_labels == (
        "O",
        "O",
        "B-org.ent.pressagency.havas",
    )


def test_parse_tsv_paste_defaults_missing_new_column_to_old_label() -> None:
    sequence = parse_tsv_paste(
        "Son\tO\n"
        "l\tB-org.ent.pressagency.ap\tO\n"
        "'\tI-org.ent.pressagency.ap\tO\n"
        "Associated\tI-org.ent.pressagency.ap\tB-org.ent.pressagency.ap\n"
        "Press\tI-org.ent.pressagency.ap\tI-org.ent.pressagency.ap\n"
        "tenait\tO\n"
    )

    assert sequence.tokens == ("Son", "l", "'", "Associated", "Press", "tenait")
    assert sequence.old_labels == (
        "O",
        "B-org.ent.pressagency.ap",
        "I-org.ent.pressagency.ap",
        "I-org.ent.pressagency.ap",
        "I-org.ent.pressagency.ap",
        "O",
    )
    assert sequence.new_labels == (
        "O",
        "O",
        "O",
        "B-org.ent.pressagency.ap",
        "I-org.ent.pressagency.ap",
        "O",
    )


def test_parse_tsv_paste_ignores_fence_markers_but_parses_tsv_inside() -> None:
    sequence = parse_tsv_paste(
        "```text\n"
        "die     O\n"
        "Austria B-org.ent.pressagency.apa\n"
        "-       I-org.ent.pressagency.apa\n"
        "Presse  I-org.ent.pressagency.apa\n"
        "-       I-org.ent.pressagency.apa\n"
        "Agentur I-org.ent.pressagency.apa\n"
        "(       I-org.ent.pressagency.apa o\n"
        "APA     I-org.ent.pressagency.apa B-org.ent.pressagency.apa\n"
        ")       I-org.ent.pressagency.apa o\n"
        "meldet  O\n"
        "```\n"
    )

    assert sequence.tokens == ("die", "Austria", "-", "Presse", "-", "Agentur", "(", "APA", ")", "meldet")
    assert sequence.new_labels == (
        "O",
        "B-org.ent.pressagency.apa",
        "I-org.ent.pressagency.apa",
        "I-org.ent.pressagency.apa",
        "I-org.ent.pressagency.apa",
        "I-org.ent.pressagency.apa",
        "O",
        "B-org.ent.pressagency.apa",
        "O",
        "O",
    )


def test_parse_tsv_paste_keeps_hyphen_token_from_two_column_tsv() -> None:
    sequence = parse_tsv_paste(
        "die     O\n"
        "Austria B-org.ent.pressagency.apa\n"
        "-       I-org.ent.pressagency.apa\n"
        "Presse  I-org.ent.pressagency.apa\n"
        "-       I-org.ent.pressagency.apa\n"
        "Agentur I-org.ent.pressagency.apa\n"
        "(       I-org.ent.pressagency.apa o\n"
        "APA     I-org.ent.pressagency.apa B-org.ent.pressagency.apa\n"
        ")       I-org.ent.pressagency.apa o\n"
        "meldet  O\n"
    )

    assert sequence.tokens == ("die", "Austria", "-", "Presse", "-", "Agentur", "(", "APA", ")", "meldet")
    assert targets_from_new_labels(sequence) == [
        PatchTarget("org.ent.pressagency.apa", 1, 6),
        PatchTarget("org.ent.pressagency.apa", 7, 8),
    ]


def test_parse_tsv_paste_rejects_bare_hyphen_without_label_in_labeled_block() -> None:
    with pytest.raises(ValueError, match="OLD/NERTAG label for every token row"):
        parse_tsv_paste(
            "die     O\n"
            "Austria B-org.ent.pressagency.apa\n"
            "-\n"
            "Presse  I-org.ent.pressagency.apa\n"
        )


def test_target_from_new_labels_ignores_unchanged_old_new_entity() -> None:
    sequence = parse_tsv_paste(
        "LAgence\tO\tO\n"
        "Stefani\tB-org.ent.pressagency.stefani\tB-org.ent.pressagency.stefani\n"
        "annonce\tO\tO\n"
    )

    assert target_from_new_labels(sequence, {"org.ent.pressagency.stefani": {"canonical_id": "stefani", "label": "org.ent.pressagency.stefani"}}) is None


def test_target_from_new_labels_uses_old_span_for_removal() -> None:
    sequence = parse_tsv_paste(
        "qui\tO\tO\n"
        "encore\tB-org.ent.radiostation.deutsche-welle\tO\n"
        "longtemps\tI-org.ent.radiostation.deutsche-welle\tO\n"
        "complémentaire\tO\tO\n"
    )

    assert target_from_new_labels(sequence) == PatchTarget("O", 1, 3)


def test_parse_tsv_paste_ignores_terminal_color_codes() -> None:
    sequence = parse_tsv_paste(
        "\x1b[2m# document_id = doc-1\x1b[0m\n"
        "TOKEN\tNERTAG\n"
        "\x1b[31;1mPalach\x1b[0m\tO\n"
        "\x1b[31;1mPress\x1b[0m\tO\n"
    )

    assert sequence.metadata["document_id"] == "doc-1"
    assert sequence.tokens == ("Palach", "Press")


def test_find_token_matches_accepts_multiple_hits() -> None:
    sequence = parse_tsv_paste("Havas\tO\n")
    rows = [{"id": "doc-1", "tokens": ["Havas", "et", "Havas"]}]

    matches = find_token_matches(rows, sequence)

    assert [(match.token_start, match.token_stop) for match in matches] == [(0, 1), (2, 3)]


def test_actionable_matches_skips_already_correct_label() -> None:
    sequence = parse_tsv_paste("Deutsche O\nWelle O\n")
    rows = [
        {
            "id": "done",
            "tokens": ["Deutsche", "Welle"],
            "token_labels": [
                "B-org.ent.radiostation.deutsche-welle",
                "I-org.ent.radiostation.deutsche-welle",
            ],
            "entities": [
                {
                    "label": "org.ent.radiostation.deutsche-welle",
                    "token_start": 0,
                    "token_stop": 2,
                }
            ],
        },
        {
            "id": "todo",
            "tokens": ["Deutsche", "Welle"],
            "token_labels": ["O", "O"],
        },
    ]

    pairs = actionable_target_pairs(
        find_token_matches(rows, sequence),
        [PatchTarget("org.ent.radiostation.deutsche-welle", 0, 2)],
    )

    assert [pair.match.row["id"] for pair in pairs] == ["todo"]


def test_actionable_matches_for_o_requires_non_o_label() -> None:
    sequence = parse_tsv_paste("Havas O\n")
    rows = [
        {"id": "done", "tokens": ["Havas"], "token_labels": ["O"]},
        {"id": "todo", "tokens": ["Havas"], "token_labels": ["B-org.ent.pressagency.havas"]},
    ]

    pairs = actionable_target_pairs(find_token_matches(rows, sequence), [PatchTarget("O", 0, 1)])

    assert [pair.match.row["id"] for pair in pairs] == ["todo"]


def test_actionable_target_pairs_are_target_specific() -> None:
    match = find_token_matches(
        [
            {
                "id": "doc-1",
                "tokens": ["A", "B", "and", "C"],
                "token_labels": [
                    "B-org.ent.pressagency.ap",
                    "I-org.ent.pressagency.ap",
                    "O",
                    "B-org.ent.pressagency.havas",
                ],
                "entities": [
                    {
                        "label": "org.ent.pressagency.ap",
                        "token_start": 0,
                        "token_stop": 2,
                    }
                ],
            }
        ],
        parse_tsv_paste("A\tO\nB\tO\nand\tO\nC\tO\n"),
    )[0]

    pairs = actionable_target_pairs(
        [match],
        [
            PatchTarget("org.ent.pressagency.ap", 0, 2),
            PatchTarget("org.ent.pressagency.reuters", 3, 4),
        ],
    )

    assert pairs == [ActionableTarget(match=match, target=PatchTarget("org.ent.pressagency.reuters", 3, 4))]


def test_actionable_target_requires_exact_entity_boundary_when_bio_labels_match() -> None:
    match = find_token_matches(
        [
            {
                "id": "doc-1",
                "tokens": ["Agence", "Havas", "."],
                "token_labels": [
                    "B-org.ent.pressagency.havas",
                    "I-org.ent.pressagency.havas",
                    "O",
                ],
                "entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "token_start": 0,
                        "token_stop": 3,
                    }
                ],
            }
        ],
        parse_tsv_paste("Agence\tO\nHavas\tO\n"),
    )[0]

    pairs = actionable_target_pairs(
        [match],
        [PatchTarget("org.ent.pressagency.havas", 0, 2)],
    )

    assert pairs == [ActionableTarget(match=match, target=PatchTarget("org.ent.pressagency.havas", 0, 2))]


def test_actionable_target_requires_entity_record_when_bio_labels_match() -> None:
    match = find_token_matches(
        [
            {
                "id": "doc-1",
                "tokens": ["Agence", "Havas"],
                "token_labels": [
                    "B-org.ent.pressagency.havas",
                    "I-org.ent.pressagency.havas",
                ],
                "entities": [],
            }
        ],
        parse_tsv_paste("Agence\tO\nHavas\tO\n"),
    )[0]

    pairs = actionable_target_pairs(
        [match],
        [PatchTarget("org.ent.pressagency.havas", 0, 2)],
    )

    assert pairs == [ActionableTarget(match=match, target=PatchTarget("org.ent.pressagency.havas", 0, 2))]


def test_parse_match_selection_accepts_numbers_and_ranges() -> None:
    assert parse_match_selection("1,3-4", 5) == [0, 2, 3]
    assert parse_match_selection("all", 3) == [0, 1, 2]
    assert parse_match_selection("", 3) == []


def test_match_context_shows_three_tokens_on_each_side() -> None:
    sequence = parse_tsv_paste("d O\ne O\n")
    row = {"id": "doc", "tokens": ["a", "b", "c", "d", "e", "f", "g", "h", "i"]}
    match = find_token_matches([row], sequence)[0]

    assert match_context(match) == "a b c [d e] f g h ..."


def test_resolve_label_accepts_known_short_alias_only() -> None:
    metadata = {
        "org.ent.pressagency.ata": {
            "canonical_id": "ata",
            "label": "org.ent.pressagency.ata",
        }
    }

    assert resolve_label("ata", metadata) == "org.ent.pressagency.ata"
    assert resolve_label("org.ent.pressagency.ata", metadata) == "org.ent.pressagency.ata"
    assert resolve_label("O", metadata) == "O"
    with pytest.raises(ValueError, match="unknown"):
        resolve_label("org.ent.pressagency.not-real", metadata)


def test_build_accepted_patches_from_tsv_can_be_applied(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "language": "fr",
                "date": "1950-01-01",
                "newspaper": "EXP",
                "text": "Havas et Havas",
                "tokens": ["Havas", "et", "Havas"],
                "token_start_offsets": [0, 6, 9],
                "token_end_offsets": [5, 8, 14],
                "token_labels": ["O", "O", "O"],
                "entities": [],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="havas",
        pasted_tsv="Havas\tO\n",
        reviewer="tester",
        label_metadata={
            "org.ent.pressagency.havas": {
                "canonical_id": "havas",
                "label": "org.ent.pressagency.havas",
            }
        },
    )

    assert summary["matches"] == 2
    assert summary["new_decisions"] == 2
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
        target_label="org.ent.pressagency.havas",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["audit_marks_written"] == 2
    assert result["applied"] == 2
    assert row["token_labels"] == ["B-org.ent.pressagency.havas", "O", "B-org.ent.pressagency.havas"]
    assert [entity["surface"] for entity in row["entities"]] == ["Havas", "Havas"]
    assert row["audit_marks"] == [
        {
            "audit_id": "manual-tsv-train",
            "decision": "accept",
            "label": "org.ent.pressagency.havas",
            "start": 0,
            "status": "verified",
            "stop": 5,
        },
        {
            "audit_id": "manual-tsv-train",
            "decision": "accept",
            "label": "org.ent.pressagency.havas",
            "start": 9,
            "status": "verified",
            "stop": 14,
        },
    ]


def test_build_accepted_patches_distinguishes_old_label_mismatch(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "Agence Havas",
                "tokens": ["Agence", "Havas"],
                "token_start_offsets": [0, 7],
                "token_end_offsets": [6, 12],
                "token_labels": ["O", "B-org.ent.pressagency.havas"],
                "entities": [],
            }
        ],
    )

    with pytest.raises(ValueError, match="token sequence found, but OLD/NERTAG labels did not match"):
        build_accepted_patches(
            input_jsonl=input_jsonl,
            candidates_path=candidates,
            decisions_path=decisions,
            audit_id="manual-tsv-train",
            label="O",
            pasted_tsv="Agence\tB-org.ent.pressagency.havas\tO\nHavas\tI-org.ent.pressagency.havas\tO\n",
            reviewer="tester",
        )


def test_build_o_patches_from_tsv_removes_overlapping_entity(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "Agence Havas",
                "tokens": ["Agence", "Havas"],
                "token_start_offsets": [0, 7],
                "token_end_offsets": [6, 12],
                "token_labels": ["B-org.ent.pressagency.havas", "I-org.ent.pressagency.havas"],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.havas",
                        "start": 0,
                        "stop": 12,
                        "surface": "Agence Havas",
                        "token_start": 0,
                        "token_stop": 2,
                    }
                ],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="O",
        pasted_tsv="Agence\tB-org.ent.pressagency.havas\nHavas\tI-org.ent.pressagency.havas\n",
        reviewer="tester",
    )

    assert summary["label"] == "O"
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    change = json.loads((tmp_path / "changes.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert result["audit_marks_written"] == 1
    assert result["applied"] == 1
    assert row["token_labels"] == ["O", "O"]
    assert row["entities"] == []
    assert row["audit_marks"] == [
        {
            "audit_id": "manual-tsv-train",
            "decision": "accept",
            "label": "O",
            "start": 0,
            "status": "verified",
            "stop": 12,
        }
    ]
    assert change["label"] == "O"
    assert change["removed_labels"] == "org.ent.pressagency.havas"


def test_build_patches_from_three_column_tsv_uses_new_column_target(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "qui restera encore longtemps complémentaire",
                "tokens": ["qui", "restera", "encore", "longtemps", "complémentaire"],
                "token_start_offsets": [0, 4, 12, 19, 29],
                "token_end_offsets": [3, 11, 18, 28, 43],
                "token_labels": [
                    "O",
                    "O",
                    "B-org.ent.radiostation.deutsche-welle",
                    "I-org.ent.radiostation.deutsche-welle",
                    "O",
                ],
                "entities": [
                    {
                        "entity_family": "radiostation",
                        "label": "org.ent.radiostation.deutsche-welle",
                        "start": 12,
                        "stop": 28,
                        "surface": "encore longtemps",
                        "token_start": 2,
                        "token_stop": 4,
                    }
                ],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="O",
        pasted_tsv=(
            "qui\tO\tO\n"
            "restera\tO\tO\n"
            "encore\tB-org.ent.radiostation.deutsche-welle\tO\n"
            "longtemps\tI-org.ent.radiostation.deutsche-welle\tO\n"
            "complémentaire\tO\tO\n"
        ),
        reviewer="tester",
        target_span=(2, 4),
    )

    assert summary["label"] == "O"
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
        replace_overlaps=True,
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["applied"] == 1
    assert row["token_labels"] == ["O", "O", "O", "O", "O"]
    assert row["entities"] == []


def test_three_column_boundary_shrink_is_actionable_when_target_span_already_correct(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "AP).",
                "tokens": ["AP", ")", "."],
                "token_start_offsets": [0, 2, 3],
                "token_end_offsets": [2, 3, 4],
                "token_labels": [
                    "B-org.ent.pressagency.ap",
                    "I-org.ent.pressagency.ap",
                    "I-org.ent.pressagency.ap",
                ],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.ap",
                        "start": 0,
                        "stop": 4,
                        "surface": "AP).",
                        "token_start": 0,
                        "token_stop": 3,
                    }
                ],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="",
        pasted_tsv=(
            "AP\tB-org.ent.pressagency.ap\tB-org.ent.pressagency.ap\n"
            ")\tI-org.ent.pressagency.ap\tO\n"
            ".\tI-org.ent.pressagency.ap\tO\n"
        ),
        reviewer="tester",
    )

    assert summary["new_decisions"] == 1
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
        replace_overlaps=True,
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["applied"] == 1
    assert row["token_labels"] == ["B-org.ent.pressagency.ap", "O", "O"]
    assert row["entities"][0]["surface"] == "AP"


def test_newer_overlapping_tsv_decision_wins_by_review_time(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    text = "l'agence de presse autrichienne APA."
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": text,
                "tokens": ["l", "'", "agence", "de", "presse", "autrichienne", "APA", "."],
                "token_start_offsets": [0, 1, 2, 9, 12, 19, 32, 35],
                "token_end_offsets": [1, 2, 8, 11, 18, 31, 35, 36],
                "token_labels": [
                    "O",
                    "O",
                    "B-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "O",
                ],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.apa",
                        "start": 2,
                        "stop": 35,
                        "surface": "agence de presse autrichienne APA",
                        "token_start": 2,
                        "token_stop": 7,
                    }
                ],
            }
        ],
    )
    build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="org.ent.pressagency.apa",
        pasted_tsv="agence\tB-org.ent.pressagency.apa\nde\tI-org.ent.pressagency.apa\npresse\tI-org.ent.pressagency.apa\nautrichienne\tI-org.ent.pressagency.apa\nAPA\tI-org.ent.pressagency.apa\n",
        reviewer="tester",
        include_existing=True,
    )
    build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="",
        pasted_tsv=(
            "l\tO\n"
            "'\tO\n"
            "agence\tB-org.ent.pressagency.apa\to\n"
            "de\tI-org.ent.pressagency.apa\to\n"
            "presse\tI-org.ent.pressagency.apa\to\n"
            "autrichienne\tI-org.ent.pressagency.apa\to\n"
            "APA\tI-org.ent.pressagency.apa\tB-org.ent.pressagency.apa\n"
            ".\tO\n"
        ),
        reviewer="tester",
    )
    decision_rows = [json.loads(line) for line in decisions.read_text(encoding="utf-8").splitlines()]
    for row in decision_rows:
        if row["source"]["surface"] == "agence de presse autrichienne APA":
            row["reviewed_at"] = "2026-08-06T00:39:50+02:00"
        if row["source"]["surface"] == "APA":
            row["reviewed_at"] = "2026-08-22T10:52:18+02:00"
    write_jsonl(decisions, decision_rows)

    apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert row["entities"] == [
        {
            "entity_family": "pressagency",
            "label": "org.ent.pressagency.apa",
            "start": 32,
            "stop": 35,
            "surface": "APA",
            "token_start": 6,
            "token_stop": 7,
        }
    ]
    assert row["token_labels"] == ["O", "O", "O", "O", "O", "O", "B-org.ent.pressagency.apa", "O"]


def test_build_patches_reports_already_queued_decision(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "Union berichtet",
                "tokens": ["Union", "berichtet"],
                "token_start_offsets": [0, 6],
                "token_end_offsets": [5, 15],
                "token_labels": ["O", "B-org.ent.pressagency.wolff"],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.wolff",
                        "start": 6,
                        "stop": 15,
                        "surface": "berichtet",
                        "token_start": 1,
                        "token_stop": 2,
                    }
                ],
            }
        ],
    )
    pasted = "Union\tO\nberichtet\tB-org.ent.pressagency.wolff\to\n"

    first = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="",
        pasted_tsv=pasted,
        reviewer="tester",
    )
    second = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="",
        pasted_tsv=pasted,
        reviewer="tester",
    )

    assert first["new_decisions"] == 1
    assert first["existing_decisions"] == 0
    assert second["new_decisions"] == 0
    assert second["existing_decisions"] == 1


def test_newer_tsv_decision_wins_for_same_source_span(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "Union berichtet",
                "tokens": ["Union", "berichtet"],
                "token_start_offsets": [0, 6],
                "token_end_offsets": [5, 15],
                "token_labels": ["O", "B-org.ent.pressagency.wolff"],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.wolff",
                        "start": 6,
                        "stop": 15,
                        "surface": "berichtet",
                        "token_start": 1,
                        "token_stop": 2,
                    }
                ],
            }
        ],
    )
    positive = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="org.ent.pressagency.wolff",
        pasted_tsv="berichtet\tB-org.ent.pressagency.wolff\n",
        reviewer="tester",
        include_existing=True,
    )
    removal = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="",
        pasted_tsv="Union\tO\nberichtet\tB-org.ent.pressagency.wolff\to\n",
        reviewer="tester",
    )

    assert positive["new_decisions"] == 1
    assert removal["new_decisions"] == 1
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["applied"] == 1
    assert row["entities"] == []
    assert row["token_labels"] == ["O", "O"]


def test_three_column_context_rows_do_not_require_prompted_label() -> None:
    sequence = parse_tsv_paste(
        "fpondent\tO\tO\n"
        "der\tO\tO\n"
        "Agentur\tB-org.ent.pressagency.havas\tO\n"
        "Haoas\tI-org.ent.pressagency.havas\tB-org.ent.pressagency.havas\n"
        "wird\tO\tO\n"
    )

    assert target_from_new_labels(
        sequence,
        {
            "org.ent.pressagency.havas": {
                "canonical_id": "havas",
                "label": "org.ent.pressagency.havas",
            }
        },
        ) == PatchTarget("org.ent.pressagency.havas", 3, 4)


def test_targets_from_new_labels_accepts_two_mentions() -> None:
    sequence = parse_tsv_paste(
        "Agence\tB-org.ent.pressagency.kipa\n"
        "de\tI-org.ent.pressagency.kipa\n"
        "presse\tI-org.ent.pressagency.kipa\n"
        "internationale\tI-org.ent.pressagency.kipa\n"
        "catholique\tI-org.ent.pressagency.kipa\n"
        "(\tI-org.ent.pressagency.kipa\to\n"
        "APC\tI-org.ent.pressagency.kipa\tB-org.ent.pressagency.kipa\n"
        ")\tI-org.ent.pressagency.kipa\to\n"
    )

    assert targets_from_new_labels(
        sequence,
        {
            "org.ent.pressagency.kipa": {
                "canonical_id": "kipa",
                "label": "org.ent.pressagency.kipa",
            }
        },
    ) == [
        PatchTarget("org.ent.pressagency.kipa", 0, 5),
        PatchTarget("org.ent.pressagency.kipa", 6, 7),
    ]


def test_targets_from_new_labels_ignores_unchanged_context_entity() -> None:
    sequence = parse_tsv_paste(
        "A\tB-org.ent.pressagency.ap\tB-org.ent.pressagency.ap\n"
        "B\tI-org.ent.pressagency.ap\tI-org.ent.pressagency.ap\n"
        "and\tO\tO\n"
        "C\tB-org.ent.pressagency.havas\tB-org.ent.pressagency.reuters\n"
    )

    assert targets_from_new_labels(
        sequence,
        {
            "org.ent.pressagency.ap": {"canonical_id": "ap", "label": "org.ent.pressagency.ap"},
            "org.ent.pressagency.havas": {"canonical_id": "havas", "label": "org.ent.pressagency.havas"},
            "org.ent.pressagency.reuters": {"canonical_id": "reuters", "label": "org.ent.pressagency.reuters"},
        },
    ) == [PatchTarget("org.ent.pressagency.reuters", 3, 4)]


def test_targets_from_new_labels_removal_uses_old_span() -> None:
    sequence = parse_tsv_paste(
        "Agence\tB-org.ent.pressagency.havas\tO\n"
        "Havas\tI-org.ent.pressagency.havas\tO\n"
    )

    assert targets_from_new_labels(sequence) == [PatchTarget("O", 0, 2)]


def test_targets_from_new_labels_relabel_uses_new_label() -> None:
    sequence = parse_tsv_paste("Havas\tB-org.ent.pressagency.havas\tB-org.ent.pressagency.reuters\n")

    assert targets_from_new_labels(
        sequence,
        {
            "org.ent.pressagency.havas": {"canonical_id": "havas", "label": "org.ent.pressagency.havas"},
            "org.ent.pressagency.reuters": {"canonical_id": "reuters", "label": "org.ent.pressagency.reuters"},
        },
    ) == [PatchTarget("org.ent.pressagency.reuters", 0, 1)]


def test_targets_from_new_labels_shortening_keeps_new_shorter_span() -> None:
    sequence = parse_tsv_paste(
        "Agence\tB-org.ent.pressagency.havas\tB-org.ent.pressagency.havas\n"
        "Havas\tI-org.ent.pressagency.havas\tI-org.ent.pressagency.havas\n"
        ".\tI-org.ent.pressagency.havas\tO\n"
    )

    assert targets_from_new_labels(
        sequence,
        {
            "org.ent.pressagency.havas": {"canonical_id": "havas", "label": "org.ent.pressagency.havas"},
        },
    ) == [PatchTarget("org.ent.pressagency.havas", 0, 2)]


def test_targets_from_new_labels_split_long_form_and_acronym_without_unchanged_context() -> None:
    sequence = parse_tsv_paste(
        "die\tO\tO\n"
        "Austria\tB-org.ent.pressagency.apa\tB-org.ent.pressagency.apa\n"
        "-\tI-org.ent.pressagency.apa\tI-org.ent.pressagency.apa\n"
        "Presse\tI-org.ent.pressagency.apa\tI-org.ent.pressagency.apa\n"
        "-\tI-org.ent.pressagency.apa\tI-org.ent.pressagency.apa\n"
        "Agentur\tI-org.ent.pressagency.apa\tI-org.ent.pressagency.apa\n"
        "(\tI-org.ent.pressagency.apa\tO\n"
        "APA\tI-org.ent.pressagency.apa\tB-org.ent.pressagency.apa\n"
        ")\tI-org.ent.pressagency.apa\tO\n"
        "meldet\tO\tO\n"
    )

    assert targets_from_new_labels(
        sequence,
        {
            "org.ent.pressagency.apa": {"canonical_id": "apa", "label": "org.ent.pressagency.apa"},
        },
    ) == [
        PatchTarget("org.ent.pressagency.apa", 1, 6),
        PatchTarget("org.ent.pressagency.apa", 7, 8),
    ]


def test_targets_from_new_labels_delete_one_and_relabel_another() -> None:
    sequence = parse_tsv_paste(
        "A\tB-org.ent.pressagency.ap\tO\n"
        "and\tO\tO\n"
        "B\tB-org.ent.pressagency.havas\tB-org.ent.pressagency.reuters\n"
    )

    assert targets_from_new_labels(
        sequence,
        {
            "org.ent.pressagency.ap": {"canonical_id": "ap", "label": "org.ent.pressagency.ap"},
            "org.ent.pressagency.havas": {"canonical_id": "havas", "label": "org.ent.pressagency.havas"},
            "org.ent.pressagency.reuters": {"canonical_id": "reuters", "label": "org.ent.pressagency.reuters"},
        },
    ) == [
        PatchTarget("O", 0, 1),
        PatchTarget("org.ent.pressagency.reuters", 2, 3),
    ]


def test_targets_from_new_labels_delete_one_and_create_another() -> None:
    sequence = parse_tsv_paste(
        "A\tB-org.ent.pressagency.ap\tO\n"
        "and\tO\tO\n"
        "B\tO\tB-org.ent.pressagency.reuters\n"
    )

    assert targets_from_new_labels(
        sequence,
        {
            "org.ent.pressagency.ap": {"canonical_id": "ap", "label": "org.ent.pressagency.ap"},
            "org.ent.pressagency.reuters": {"canonical_id": "reuters", "label": "org.ent.pressagency.reuters"},
        },
    ) == [
        PatchTarget("O", 0, 1),
        PatchTarget("org.ent.pressagency.reuters", 2, 3),
    ]


def test_multi_mention_tsv_patch_splits_long_form_and_acronym(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    text = "Agence de presse internationale catholique (APC)."
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": text,
                "tokens": ["Agence", "de", "presse", "internationale", "catholique", "(", "APC", ")", "."],
                "token_start_offsets": [0, 7, 10, 17, 32, 43, 44, 47, 48],
                "token_end_offsets": [6, 9, 16, 31, 42, 44, 47, 48, 49],
                "token_labels": [
                    "B-org.ent.pressagency.kipa",
                    "I-org.ent.pressagency.kipa",
                    "I-org.ent.pressagency.kipa",
                    "I-org.ent.pressagency.kipa",
                    "I-org.ent.pressagency.kipa",
                    "I-org.ent.pressagency.kipa",
                    "I-org.ent.pressagency.kipa",
                    "I-org.ent.pressagency.kipa",
                    "O",
                ],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.kipa",
                        "start": 0,
                        "stop": 48,
                        "surface": "Agence de presse internationale catholique (APC)",
                        "token_start": 0,
                        "token_stop": 8,
                    }
                ],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="",
        pasted_tsv=(
            "Agence\tB-org.ent.pressagency.kipa\n"
            "de\tI-org.ent.pressagency.kipa\n"
            "presse\tI-org.ent.pressagency.kipa\n"
            "internationale\tI-org.ent.pressagency.kipa\n"
            "catholique\tI-org.ent.pressagency.kipa\n"
            "(\tI-org.ent.pressagency.kipa\to\n"
            "APC\tI-org.ent.pressagency.kipa\tB-org.ent.pressagency.kipa\n"
            ")\tI-org.ent.pressagency.kipa\to\n"
            ".\tO\n"
        ),
        reviewer="tester",
        label_metadata={
            "org.ent.pressagency.kipa": {
                "canonical_id": "kipa",
                "label": "org.ent.pressagency.kipa",
            }
        },
    )

    assert summary["new_decisions"] == 2
    assert summary["mentions"] == 2
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["applied"] == 2
    assert row["token_labels"] == [
        "B-org.ent.pressagency.kipa",
        "I-org.ent.pressagency.kipa",
        "I-org.ent.pressagency.kipa",
        "I-org.ent.pressagency.kipa",
        "I-org.ent.pressagency.kipa",
        "O",
        "B-org.ent.pressagency.kipa",
        "O",
        "O",
    ]
    assert [entity["surface"] for entity in row["entities"]] == [
        "Agence de presse internationale catholique",
        "APC",
    ]


def test_mixed_removal_and_relabel_tsv_patch_writes_target_specific_candidates(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    text = "A and B"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": text,
                "tokens": ["A", "and", "B"],
                "token_start_offsets": [0, 2, 6],
                "token_end_offsets": [1, 5, 7],
                "token_labels": [
                    "B-org.ent.pressagency.ap",
                    "O",
                    "B-org.ent.pressagency.havas",
                ],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.ap",
                        "start": 0,
                        "stop": 1,
                        "surface": "A",
                        "token_start": 0,
                        "token_stop": 1,
                    },
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.havas",
                        "start": 6,
                        "stop": 7,
                        "surface": "B",
                        "token_start": 2,
                        "token_stop": 3,
                    },
                ],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="",
        pasted_tsv=(
            "A\tB-org.ent.pressagency.ap\tO\n"
            "and\tO\tO\n"
            "B\tB-org.ent.pressagency.havas\tB-org.ent.pressagency.reuters\n"
        ),
        reviewer="tester",
        label_metadata={
            "org.ent.pressagency.ap": {"canonical_id": "ap", "label": "org.ent.pressagency.ap"},
            "org.ent.pressagency.havas": {"canonical_id": "havas", "label": "org.ent.pressagency.havas"},
            "org.ent.pressagency.reuters": {"canonical_id": "reuters", "label": "org.ent.pressagency.reuters"},
        },
    )

    written_candidates = [json.loads(line) for line in candidates.read_text(encoding="utf-8").splitlines()]
    candidate_labels = [
        candidate["predicted_entities"][0]["label"]
        for candidate in written_candidates
    ]
    candidate_surfaces = [
        candidate["predicted_entities"][0]["surface"]
        for candidate in written_candidates
    ]
    assert summary["matches"] == 1
    assert summary["mentions"] == 2
    assert summary["new_candidates"] == 2
    assert candidate_labels == ["O", "org.ent.pressagency.reuters"]
    assert candidate_surfaces == ["A", "B"]


def test_apply_tsv_entity_patch_replaces_overlapping_boundary(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "LAgence Stefani annonce",
                "tokens": ["LAgence", "Stefani", "annonce"],
                "token_start_offsets": [0, 8, 16],
                "token_end_offsets": [7, 15, 23],
                "token_labels": ["O", "B-org.ent.pressagency.stefani", "O"],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.stefani",
                        "start": 8,
                        "stop": 15,
                        "surface": "Stefani",
                        "token_start": 1,
                        "token_stop": 2,
                    }
                ],
            }
        ],
    )

    build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="org.ent.pressagency.stefani",
        pasted_tsv="LAgence\tO\nStefani\tB-org.ent.pressagency.stefani\n",
        reviewer="tester",
        include_existing=True,
    )
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
        replace_overlaps=True,
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["applied"] == 1
    assert row["token_labels"] == ["B-org.ent.pressagency.stefani", "I-org.ent.pressagency.stefani", "O"]
    assert row["entities"] == [
        {
            "entity_family": "pressagency",
            "label": "org.ent.pressagency.stefani",
            "start": 0,
            "stop": 15,
            "surface": "LAgence Stefani",
            "token_start": 0,
            "token_stop": 2,
        }
    ]


def test_apply_apa_tsv_split_replaces_original_wide_entity(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    text = "die Austria - Presse - Agentur ( APA ) meldet"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": text,
                "tokens": ["die", "Austria", "-", "Presse", "-", "Agentur", "(", "APA", ")", "meldet"],
                "token_start_offsets": [0, 4, 12, 14, 21, 23, 31, 33, 37, 39],
                "token_end_offsets": [3, 11, 13, 20, 22, 30, 32, 36, 38, 45],
                "token_labels": [
                    "O",
                    "B-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "I-org.ent.pressagency.apa",
                    "O",
                ],
                "entities": [
                    {
                        "entity_family": "pressagency",
                        "label": "org.ent.pressagency.apa",
                        "start": 4,
                        "stop": 38,
                        "surface": "Austria - Presse - Agentur ( APA )",
                        "token_start": 1,
                        "token_stop": 9,
                    }
                ],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="",
        pasted_tsv=(
            "die\tO\n"
            "Austria\tB-org.ent.pressagency.apa\n"
            "-\tI-org.ent.pressagency.apa\n"
            "Presse\tI-org.ent.pressagency.apa\n"
            "-\tI-org.ent.pressagency.apa\n"
            "Agentur\tI-org.ent.pressagency.apa\n"
            "(\tI-org.ent.pressagency.apa\to\n"
            "APA\tI-org.ent.pressagency.apa\tB-org.ent.pressagency.apa\n"
            ")\tI-org.ent.pressagency.apa\to\n"
            "meldet\tO\n"
        ),
        reviewer="tester",
        label_metadata={
            "org.ent.pressagency.apa": {"canonical_id": "apa", "label": "org.ent.pressagency.apa"},
        },
    )
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert summary["matches"] == 1
    assert summary["mentions"] == 2
    assert result["applied"] == 2
    assert row["entities"] == [
        {
            "entity_family": "pressagency",
            "label": "org.ent.pressagency.apa",
            "start": 4,
            "stop": 30,
            "surface": "Austria - Presse - Agentur",
            "token_start": 1,
            "token_stop": 6,
        },
        {
            "entity_family": "pressagency",
            "label": "org.ent.pressagency.apa",
            "start": 33,
            "stop": 36,
            "surface": "APA",
            "token_start": 7,
            "token_stop": 8,
        },
    ]
    assert row["token_labels"] == [
        "O",
        "B-org.ent.pressagency.apa",
        "I-org.ent.pressagency.apa",
        "I-org.ent.pressagency.apa",
        "I-org.ent.pressagency.apa",
        "I-org.ent.pressagency.apa",
        "O",
        "B-org.ent.pressagency.apa",
        "O",
        "O",
    ]
    assert row["token_labels"] == labels_from_entities(row)


def test_build_o_patches_from_tsv_audits_already_empty_span(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        input_jsonl,
        [
            {
                "id": "doc-1",
                "document_id": "doc-1",
                "text": "Radio Test",
                "tokens": ["Radio", "Test"],
                "token_start_offsets": [0, 6],
                "token_end_offsets": [5, 10],
                "token_labels": ["O", "O"],
                "entities": [],
            }
        ],
    )

    summary = build_accepted_patches(
        input_jsonl=input_jsonl,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        label="O",
        pasted_tsv="Radio\tO\nTest\tO\n",
        reviewer="tester",
        include_existing=True,
    )

    assert summary["label"] == "O"
    result = apply_span_patches(
        input_jsonl=input_jsonl,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="manual-tsv-train",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["applied"] == 0
    assert result["audit_marks_written"] == 1
    assert row["entities"] == []
    assert row["token_labels"] == ["O", "O"]
    assert row["audit_marks"] == [
        {
            "audit_id": "manual-tsv-train",
            "decision": "accept",
            "label": "O",
            "start": 0,
            "status": "verified",
            "stop": 10,
        }
    ]
    assert (tmp_path / "changes.jsonl").read_text(encoding="utf-8") == ""
