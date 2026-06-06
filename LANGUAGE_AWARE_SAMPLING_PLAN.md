# Language-Aware Sampling Plan

## Goal

Make coverage analysis and targeted sampling language-aware. A label should not be considered sufficiently covered only because it has many examples in one language. Coverage targets are per label and per language.

Default language groups:

- Main languages: `de`, `fr`, `en`
- Side languages: `lb`, `it`

Default targets:

- Main languages: 20 accepted examples per label-language bucket
- Side languages: 5 accepted examples per label-language bucket

All values must be configurable from `configs/model-v0.1.0.mk` or command-line overrides.

## Implementation Steps

1. Extend `lib.annotation_stats`:
   - Keep existing label-level totals for backward compatibility.
   - Add per-language counts and missing-to-target values under each row.
   - Add flattened TSV columns for configured language targets.
   - Add summary metadata for language targets and undercovered label-language buckets.
2. Add configurable defaults:
   - `ANNOTATION_MAIN_LANGS ?= de fr en`
   - `ANNOTATION_SIDE_LANGS ?= lb it`
   - `ANNOTATION_MAIN_TARGET_PER_LABEL_LANG ?= 20`
   - `ANNOTATION_SIDE_TARGET_PER_LABEL_LANG ?= 5`
   - `ANNOTATION_LANGUAGE_TARGETS ?=`
3. Update samplers:
   - Add a helper that reads undercovered `(label, language)` buckets from coverage JSON.
   - Keep `load_undercovered_labels()` as a compatibility wrapper.
   - When `--only-under-target` is set, sample only undercovered label-language pairs.
4. Update review prioritization:
   - Use row language plus label when deciding whether a row is useful for coverage.
   - Prefer rows that fill larger language-specific gaps.
5. Update Makefile/help/docs:
   - Wire language target config into `annotation-stats`.
   - Explain main/side language defaults.
6. Add tests:
   - Language-aware coverage counts.
   - Undercovered label-language extraction.
   - Sampler query filtering by undercovered language.
   - Review priority for undercovered language rows.

## Compatibility

Existing `missing_to_target`, `total`, `legacy`, `newsagency_snippets`, `radiostation_snippets`, and `pending_review` fields remain available at label level. New consumers should use `languages` or `language_rows`.
