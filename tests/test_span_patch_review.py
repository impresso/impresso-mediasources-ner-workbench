import json
from pathlib import Path

from lib.apply_span_patch_decisions import apply_span_patches
from lib.span_patch_review import decision_record, is_verified, load_span_patches, numbered_tokens, resolve_manual_correction, summarize_queue


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_load_span_patches_flattens_audit_candidates(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "language": "fr",
                "text": "foo Havas bar",
                "predicted_entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "start": 4,
                        "stop": 9,
                        "surface": "Havas",
                        "token_start": 1,
                        "token_stop": 2,
                    }
                ],
            }
        ],
    )

    patches = load_span_patches(candidates, audit_id="audit-1")

    assert len(patches) == 1
    assert patches[0]["document_id"] == "doc-1"
    assert patches[0]["suggested_label"] == "org.ent.pressagency.havas"
    assert patches[0]["summary"] == 'doc-1: "Havas" -> org.ent.pressagency.havas'
    assert patches[0]["left_context"] == "foo"
    assert patches[0]["right_context"] == "bar"
    assert patches[0]["review_id"].startswith("span-patch:audit-1:")


def test_load_span_patches_skips_verified_audit_marks(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    write_jsonl(
        candidates,
        [
            {
                "audit_marks": [
                    {
                        "audit_id": "older-audit",
                        "decision": "reject",
                        "label": "org.ent.pressagency.havas",
                        "start": 4,
                        "status": "verified",
                        "stop": 9,
                    }
                ],
                "document_id": "doc-1",
                "text": "foo Havas bar",
                "predicted_entities": [{"label": "org.ent.pressagency.havas", "start": 4, "stop": 9, "surface": "Havas"}],
            }
        ],
    )

    assert load_span_patches(candidates, audit_id="audit-1") == []


def test_decision_record_adds_verified_audit_marker(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    write_jsonl(
        candidates,
        [
                {
                    "document_id": "doc-1",
                    "text": "foo Havas bar",
                    "tokens": ["foo", "Havas", "bar"],
                    "token_start_offsets": [0, 4, 10],
                    "token_end_offsets": [3, 9, 13],
                    "predicted_entities": [
                        {
                            "label": "org.ent.pressagency.havas",
                            "start": 4,
                            "stop": 9,
                            "surface": "Havas",
                            "token_start": 1,
                            "token_stop": 2,
                        }
                    ],
                }
            ],
        )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]

    decision = decision_record(patch, choice="reject", reviewer="tester")
    skipped = decision_record(patch, choice="skip", reviewer="tester")

    assert decision["audit_marker"].startswith("tester:")
    assert decision["audit_marker"].endswith(":verified")
    assert decision["audit_status"] == "verified"
    assert is_verified(decision)
    assert decision["span"]["token_start"] == patch["token_start"]
    assert decision["span"]["token_stop"] == patch["token_stop"]
    assert skipped["audit_status"] == "skipped"
    assert not is_verified(skipped)
    assert summarize_queue([patch], {patch["review_id"]: decision})["pending"] == 0


def test_apply_span_patches_adds_accepted_entity(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    changes = tmp_path / "changes.jsonl"
    changes_tsv = tmp_path / "changes.tsv"
    summary = tmp_path / "summary.json"
    write_jsonl(
        source,
        [
            {
                "document_id": "doc-1",
                "id": "doc-1",
                "language": "fr",
                "text": "foo Havas bar",
                "tokens": ["foo", "Havas", "bar"],
                "token_start_offsets": [0, 4, 10],
                "token_end_offsets": [3, 9, 13],
                "token_labels": ["O", "O", "O"],
                "entities": [],
            }
        ],
    )
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "language": "fr",
                "text": "foo Havas bar",
                "predicted_entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "start": 4,
                        "stop": 9,
                        "surface": "Havas",
                    }
                ],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]
    write_jsonl(decisions, [decision_record(patch, choice="accept", reviewer="tester")])

    result = apply_span_patches(
        input_jsonl=source,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="audit-1",
        changes_jsonl=changes,
        changes_tsv=changes_tsv,
        summary_json=summary,
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["applied"] == 1
    assert row["token_labels"] == ["O", "B-org.ent.pressagency.havas", "O"]
    assert row["entities"] == [
        {
            "entity_family": "pressagency",
            "label": "org.ent.pressagency.havas",
            "start": 4,
            "stop": 9,
            "surface": "Havas",
            "token_start": 1,
            "token_stop": 2,
        }
    ]
    assert row["audit_marks"] == [
        {
            "audit_id": "audit-1",
            "decision": "accept",
            "label": "org.ent.pressagency.havas",
            "start": 4,
            "status": "verified",
            "stop": 9,
        }
    ]
    assert "review_id\tdocument_id" in changes_tsv.read_text(encoding="utf-8")


def test_apply_span_patches_persists_rejected_audit_mark_without_entity(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        source,
        [
            {
                "document_id": "doc-1",
                "id": "doc-1",
                "text": "foo Havas bar",
                "tokens": ["foo", "Havas", "bar"],
                "token_start_offsets": [0, 4, 10],
                "token_end_offsets": [3, 9, 13],
                "token_labels": ["O", "O", "O"],
                "entities": [],
            }
        ],
    )
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "text": "foo Havas bar",
                "predicted_entities": [{"label": "org.ent.pressagency.havas", "start": 4, "stop": 9, "surface": "Havas"}],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]
    write_jsonl(decisions, [decision_record(patch, choice="reject", reviewer="tester")])

    result = apply_span_patches(
        input_jsonl=source,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="audit-1",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert result["applied"] == 0
    assert row["entities"] == []
    assert row["token_labels"] == ["O", "O", "O"]
    assert row["audit_marks"] == [
        {
            "audit_id": "audit-1",
            "decision": "reject",
            "label": "org.ent.pressagency.havas",
            "start": 4,
            "status": "verified",
            "stop": 9,
        }
    ]


def test_apply_span_patches_uses_modified_entity(tmp_path: Path) -> None:
    source = tmp_path / "train.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    decisions = tmp_path / "decisions.jsonl"
    output = tmp_path / "patched.jsonl"
    write_jsonl(
        source,
        [
            {
                "document_id": "doc-1",
                "id": "doc-1",
                "text": "foo Agence Havas bar",
                "tokens": ["foo", "Agence", "Havas", "bar"],
                "token_start_offsets": [0, 4, 11, 17],
                "token_end_offsets": [3, 10, 16, 20],
                "token_labels": ["O", "O", "O", "O"],
                "entities": [],
            }
        ],
    )
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "text": "foo Agence Havas bar",
                "predicted_entities": [{"label": "org.ent.pressagency.reuters", "start": 11, "stop": 16, "surface": "Havas"}],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]
    write_jsonl(
        decisions,
        [
            decision_record(
                patch,
                choice="modify",
                reviewer="tester",
                correct_label="org.ent.pressagency.havas",
                start=4,
                stop=16,
                token_start=1,
                token_stop=3,
            )
        ],
    )

    apply_span_patches(
        input_jsonl=source,
        output_jsonl=output,
        candidates_path=candidates,
        decisions_path=decisions,
        audit_id="audit-1",
        changes_jsonl=tmp_path / "changes.jsonl",
        changes_tsv=tmp_path / "changes.tsv",
        summary_json=tmp_path / "summary.json",
    )

    row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert row["token_labels"] == ["O", "B-org.ent.pressagency.havas", "I-org.ent.pressagency.havas", "O"]
    assert row["audit_marks"] == [
        {
            "applied_label": "org.ent.pressagency.havas",
            "applied_start": 4,
            "applied_stop": 16,
            "audit_id": "audit-1",
            "decision": "modify",
            "label": "org.ent.pressagency.reuters",
            "start": 11,
            "status": "verified",
            "stop": 16,
        }
    ]


def test_resolve_manual_correction_from_visible_surface_text(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    text = "foo Agence Havas bar Havas baz"
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "text": text,
                "predicted_entities": [{"label": "org.ent.pressagency.reuters", "start": 17, "stop": 22, "surface": "Havas"}],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]

    assert resolve_manual_correction(patch, "Agence Havas org.ent.pressagency.havas") == (
        4,
        16,
        "org.ent.pressagency.havas",
    )
    assert resolve_manual_correction(patch, '"Agence Havas" org.ent.pressagency.havas') == (
        4,
        16,
        "org.ent.pressagency.havas",
    )


def test_resolve_manual_correction_supports_label_only_and_exact_offsets(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "text": "foo Havas bar",
                "predicted_entities": [{"label": "org.ent.pressagency.reuters", "start": 4, "stop": 9, "surface": "Havas"}],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]

    assert resolve_manual_correction(patch, "org.ent.pressagency.havas") == (4, 9, "org.ent.pressagency.havas")
    assert resolve_manual_correction(patch, "0:9 org.ent.pressagency.havas") == (0, 9, "org.ent.pressagency.havas")


def test_resolve_manual_correction_prefers_token_spans_when_offsets_are_available(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "text": "foo Agence Havas bar",
                "tokens": ["foo", "Agence", "Havas", "bar"],
                "token_start_offsets": [0, 4, 11, 17],
                "token_end_offsets": [3, 10, 16, 20],
                "predicted_entities": [{"label": "org.ent.pressagency.reuters", "start": 11, "stop": 16, "surface": "Havas"}],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]

    assert resolve_manual_correction(patch, "1:3 org.ent.pressagency.havas") == (4, 16, "org.ent.pressagency.havas")


def test_decision_record_preserves_token_span_for_manual_patch(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "text": "foo Agence Havas bar",
                "tokens": ["foo", "Agence", "Havas", "bar"],
                "token_start_offsets": [0, 4, 11, 17],
                "token_end_offsets": [3, 10, 16, 20],
                "predicted_entities": [{"label": "org.ent.pressagency.reuters", "start": 11, "stop": 16, "surface": "Havas"}],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]
    decision = decision_record(
        patch,
        choice="modify",
        reviewer="tester",
        correct_label="org.ent.pressagency.havas",
        start=4,
        stop=16,
        token_start=1,
        token_stop=3,
    )

    assert decision["span"] == {
        "label": "org.ent.pressagency.havas",
        "start": 4,
        "stop": 16,
        "token_start": 1,
        "token_stop": 3,
    }


def test_numbered_tokens_match_review_display_without_prediction_marker(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "text": "foo Havas bar",
                "tokens": ["foo", "Havas", "bar"],
                "token_start_offsets": [0, 4, 10],
                "token_end_offsets": [3, 9, 13],
                "predicted_entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "start": 4,
                        "stop": 9,
                        "surface": "Havas",
                        "token_start": 1,
                        "token_stop": 2,
                    }
                ],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]

    assert numbered_tokens(patch) == "0:foo 1:Havas 2:bar"


def test_numbered_tokens_focus_long_documents_around_prediction(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    tokens = [f"t{index}" for index in range(700)]
    text = " ".join(tokens)
    starts = []
    ends = []
    offset = 0
    for token in tokens:
        starts.append(offset)
        offset += len(token)
        ends.append(offset)
        offset += 1
    write_jsonl(
        candidates,
        [
            {
                "document_id": "doc-1",
                "text": text,
                "tokens": tokens,
                "token_start_offsets": starts,
                "token_end_offsets": ends,
                "predicted_entities": [
                    {
                        "label": "org.ent.pressagency.havas",
                        "start": starts[650],
                        "stop": ends[650],
                        "surface": "t650",
                        "token_start": 650,
                        "token_stop": 651,
                    }
                ],
            }
        ],
    )
    patch = load_span_patches(candidates, audit_id="audit-1")[0]
    rendered = numbered_tokens(patch)

    assert "650:t650" in rendered
    assert "0:t0" not in rendered
    assert "earlier tokens omitted" in rendered
    assert len([chunk for chunk in rendered.split() if ":" in chunk and chunk.split(":", 1)[0].isdigit()]) <= 513
