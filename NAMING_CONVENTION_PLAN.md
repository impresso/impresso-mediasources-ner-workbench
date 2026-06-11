# Naming Convention Plan

This plan defines the curator-facing target vocabulary for annotation workflows in this workbench. It intentionally excludes MLM, model training, evaluation, and publishing targets unless they directly support annotation curation.

The Makefile should expose canonical names only. No compatibility aliases are part of the public command surface.

## Principles

Use one lifecycle vocabulary across snippet sampling, audit queues, and dataset integration:

```text
inspect -> sample/audit -> suggest -> review -> split/apply -> preview-promote -> promote
```

Use verbs for actions and nouns for the material being acted on:

```text
make <verb>-<object>
```

Use the same verb for the same lifecycle step, even when the implementation differs:

- `sample`: collect new candidate examples from outside the dataset.
- `audit`: find candidate changes inside existing dataset rows.
- `suggest`: pre-annotate candidates with model predictions, alias matches, or heuristic candidates.
- `review`: human annotation decision step.
- `split`: convert reviewed new snippets into train/validation/test rows.
- `apply`: convert reviewed patch decisions into a patched copy of an existing split.
- `preview-promote`: show what dataset integration would do without writing.
- `promote`: integrate materialized rows or patched splits into the configured prerelease/source dataset.
- `integrate`: convenience target that runs the materialization step, previews promotion when applicable, and then promotes.

Avoid these as curator-facing verbs:

- `score`: too model-centric; use `suggest` for annotation candidates.
- `merge`: too implementation-centric; use `promote` for dataset integration.
- `export`: ambiguous because it can mean split snippets, publish dataset, or write public artifacts.
- `refresh`: unclear about what changes; use `integrate`.
- `legacy`: avoid for active HIPE-derived data; use `hipe` or `eval-disagreements` instead.

## Canonical Object Names

Use short, curator-readable objects:

| Object | Meaning |
| --- | --- |
| `newsagency-snippets` | sampled news-agency snippet candidates |
| `radio-snippets` | sampled radio-station snippet candidates |
| `existing-spans` | already accepted spans being audited for boundary/label/removal decisions |
| `span-patches` | proposed additions or corrections to existing dataset rows |
| `eval-disagreements` | train/validation/test gold-vs-prediction disagreements |
| `dataset-splits` | train/validation/test integrity checks |

Prefer `radio` in target names, not `radiostation`, because it is shorter and matches the preferred Make targets. Keep label names and paths unchanged where they use `radiostation`, because those reflect entity taxonomy and existing file layout.

## Canonical Workflows

### New Snippet Annotation

Routine coverage-driven news-agency workflow:

```bash
make annotation-stats
make sample-newsagency-snippets
make suggest-newsagency-snippet-spans
make review-newsagency-snippet-spans REVIEWER="$USER"
make split-newsagency-snippets
make preview-promote-snippets
make promote-snippets
```

Routine coverage-driven radio workflow:

```bash
make annotation-stats
make sample-radio-snippets
make suggest-radio-snippet-spans
make review-radio-snippet-spans REVIEWER="$USER"
make split-radio-snippets
make preview-promote-snippets
make promote-snippets
```

Use explicit free-sampling targets only when you deliberately do not want coverage filtering:

```bash
make sample-freely-newsagency-snippets
make sample-freely-radio-snippets
```

Use the combined integration target when reviewed snippets are ready:

```bash
make integrate-snippets
```

`integrate-snippets` runs the family split targets, previews promotion, and promotes the split rows into train/validation/test.

### Existing Span Boundary/Label Audit

Use this when an accepted annotation already exists and needs verification or correction.

```bash
make audit-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
make review-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas REVIEWER="$USER"
make apply-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
make existing-span-status SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
make promote-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

Use the combined integration target when reviewed existing-span decisions are ready:

```bash
make integrate-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

### Span Patch Audit For Missed Annotations

Use this when a model/audit suggests missing annotations in existing dataset rows.

```bash
make audit-empty-training-docs
make review-span-patches REVIEWER="$USER"
make apply-span-patches
make span-patch-status
make promote-span-patches
```

Use the combined integration target when reviewed span-patch decisions are ready:

```bash
make integrate-span-patches
```

### Evaluation Disagreement Annotation

Use this for active HIPE-derived train/validation/test gold-vs-prediction disagreement curation.

```bash
make suggest-eval-disagreements CURATION_MODEL=...
make review-curation REVIEWER="$USER"
make validate-curation
make apply-curation
```

Split-specific suggestion targets:

```bash
make suggest-eval-disagreements-train CURATION_MODEL=...
make suggest-eval-disagreements-validation CURATION_MODEL=...
make suggest-eval-disagreements-test CURATION_MODEL=...
```

`review-curation`, `validate-curation`, and `apply-curation` remain generic because they operate on the shared disagreement review directory.

## State And Diagnostics Targets

State targets should describe what they summarize and should include train, validation, and test outputs by default.

Canonical state targets:

- `annotation-stats`
- `mention-profiles`
- `curation-dashboard`
- `curation-state`
- `snippet-state`
- `eval-disagreement-state`
- `dataset-state`
- `validate-dataset-splits`

Suggested snippet state display:

```text
family        sampled  suggested  reviewed  decisions  split_rows  split_entities  statuses
newsagency        52         52        52        126          14              16  ...
radio             20         20        20        463          17              26  ...
```

## File And Variable Naming

Make target names can change faster than file layout. Keep path changes conservative.

Recommended variable policy:

- Public Make help and docs use canonical names.
- Existing config variable names may remain if changing them creates data-layout churn.
- New variables should use canonical object names where practical.
- `SNIPPET_PROMOTE_*` is acceptable because promote is canonical.

Avoid renaming entity labels or metadata files:

- Keep `org.ent.radiostation.*`.
- Keep `resources/radiostation_seeds.json`.
- Keep `data/curated/snippets/radiostations/` unless doing a planned data-layout migration.

## Target Naming Checklist

Before adding a new annotation target, verify:

- Does the verb match exactly one lifecycle step?
- Does the object identify the material being worked on?
- Would an annotator understand the target without knowing the Python module?
- Does the target avoid implementation words like `score`, `merge`, `export`, or `refresh` unless those words are truly the user-facing operation?
- Is `promote` used for dataset integration?
- Is `integrate` used for a materialize-and-promote shortcut?
- Is `apply` reserved for patching an existing split?
- Is `split` reserved for turning reviewed snippets into train/validation/test files?
- Are non-canonical target aliases absent from the Makefile and docs?
