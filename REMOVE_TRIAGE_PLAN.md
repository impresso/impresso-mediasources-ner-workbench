# Remove Radio-Station Snippet Triage

## Goal

Use one sampled-span curation workflow for both news agencies and radio stations:

```text
sample candidate text -> pre-annotate spans -> review spans -> export accepted spans
```

`snippet` remains a provenance/source term for short sampled Impresso text windows. It is no longer a separate yes/no curation mode.

## Rationale

- The training data is span-based JSONL, so the review workflow should produce accepted spans directly.
- Radio-station scoring already pre-annotates candidate spans with deterministic alias matching and optional ModernBERT predictions.
- The existing `review-radiostation-spans` target already reuses the span reviewer with radio-station metadata.
- The binary/ternary `yes`/`no`/`skip` triage step creates an extra decision format and extra materialized files without producing trainable annotations.

## Implementation Steps

1. Keep the radio-station sampling, scoring, span review, and export targets.
2. Remove the `review-radiostation-snippets` Make target and help text.
3. Remove the unused `RADIOSTATION_SNIPPET_OUTPUT_DIR` config variable.
4. Remove the dedicated `lib.review_radiostation_snippets` module.
5. Remove tests that only cover materializing `positive_snippets.jsonl`, `negative_snippets.jsonl`, and `skipped_snippets.jsonl`.
6. Update documentation to describe radio-station curation as span pre-annotation plus span review.

## Resulting Radio-Station Workflow

```bash
make sample-radiostations CFG=configs/model-v0.1.0.mk
make score-radiostation-snippets CFG=configs/model-v0.1.0.mk
make review-radiostation-spans CFG=configs/model-v0.1.0.mk REVIEWER="$USER"
make export-radiostation-snippets CFG=configs/model-v0.1.0.mk
```

Rows rejected during span review remain useful audit and negative evidence, but they are represented in the same reviewed JSONL stream rather than in separate triage files.
