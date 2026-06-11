# Naming Convention Plan

This plan defines a curator-facing naming convention for annotation workflows in this workbench. It intentionally excludes MLM, model training, evaluation, and publishing targets unless they directly support annotation curation.

The goal is that an annotator can read a Make target and know where it sits in the workflow without remembering implementation details.

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
- `refresh`: convenience target that runs the materialization step and then promotion.

Avoid these as canonical curator-facing verbs:

- `score`: too model-centric; use `suggest` for annotation candidates.
- `merge`: too implementation-centric; use `promote` for dataset integration.
- `export`: ambiguous because it can mean split snippets, publish dataset, or write public artifacts.
- `curate`: too broad for a specific target; keep only as a general documentation concept.
- `legacy`: avoid for active HIPE-derived data; use `hipe` or `eval-disagreements` instead.

Compatibility aliases can exist temporarily, but help text and documentation should only show canonical names.

## Canonical Object Names

Use short, curator-readable objects:

| Object | Meaning |
| --- | --- |
| `newsagency-snippets` | sampled news-agency snippet candidates |
| `radio-snippets` | sampled radio-station snippet candidates |
| `existing-spans` | already accepted spans being audited for boundary/label/removal decisions |
| `span-patches` | proposed additions or corrections to existing dataset rows |
| `eval-disagreements` | train/validation/test gold-vs-prediction disagreements |
| `snippet-dataset` | combined snippet split files promoted into the prerelease dataset |
| `dataset-splits` | train/validation/test integrity checks |

Prefer `radio` in target names, not `radiostation`, because it is shorter and now matches the preferred Make targets. Keep label names and paths unchanged where they use `radiostation`, because those reflect entity taxonomy and existing file layout.

## Canonical Workflows

### 1. New Snippet Annotation

For new examples gathered from Impresso search:

```bash
make annotation-stats
make sample-newsagency-snippets
make suggest-newsagency-snippet-spans
make review-newsagency-snippet-spans REVIEWER="$USER"
make split-newsagency-snippets
make preview-promote-snippets
make promote-snippets
```

For radio:

```bash
make annotation-stats
make sample-radio-snippets
make suggest-radio-snippet-spans
make review-radio-snippet-spans REVIEWER="$USER"
make split-radio-snippets
make preview-promote-snippets
make promote-snippets
```

Convenience target:

```bash
make refresh-snippet-dataset
```

Recommended target changes:

| Current target | Canonical target | Notes |
| --- | --- | --- |
| `sample-newsagencies` | `sample-newsagency-snippets` | Align object with later snippet steps. |
| `sample-needed-newsagencies` | `sample-needed-newsagency-snippets` | Coverage-driven variant. |
| `sample-radio` | `sample-radio-snippets` | Align object with later snippet steps. |
| `suggest-newsagency-snippet-spans` | keep | Good. |
| `suggest-radio-snippet-spans` | keep | Good. |
| `score-newsagency-snippets` | alias only | Replace in docs/help with `suggest-newsagency-snippet-spans`. |
| `score-radiostation-snippets` | alias only | Replace in docs/help with `suggest-radio-snippet-spans`. |
| `review-newsagency-snippet-spans` | keep | Good. |
| `review-radio-snippet-spans` | keep | Good. |
| `review-newsagency-snippets` | alias only | Too broad; does not say spans are reviewed. |
| `review-radiostation-spans` | alias only | Use radio object name consistently. |
| `split-newsagency-snippets` | keep | Good. |
| `split-radio-snippets` | keep | Good. |
| `export-newsagency-snippets` | alias only | `split` is clearer for train/validation/test materialization. |
| `export-radiostation-snippets` | alias only | Same. |
| `preview-snippet-merge` | `preview-promote-snippets` | Avoid `merge`; promote is the dataset-integration verb. |
| `merge-snippets` | `promote-snippets` | Make `promote-snippets` canonical again. |
| `refresh-snippet-dataset` | keep | Good convenience name. |
| `refresh-snippets` | alias only | Less explicit than `refresh-snippet-dataset`. |

### 2. Existing Span Boundary/Label Audit

Use this when an accepted annotation already exists and needs verification or correction.

```bash
make audit-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
make review-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas REVIEWER="$USER"
make apply-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
make preview-promote-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
make promote-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

Convenience target:

```bash
make refresh-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

Recommended target changes:

| Current target | Canonical target | Notes |
| --- | --- | --- |
| `audit-existing-spans` | keep | Good. |
| `review-existing-spans` | keep | Good. |
| `apply-existing-spans` | keep | Good because it writes a patched split, not new rows. |
| `existing-span-status` | `preview-promote-existing-spans` | Status target specifically previews promotion readiness. |
| `promote-existing-spans` | keep | Good. |
| `refresh-existing-spans` | keep | Good. |

### 3. Span Patch Audit For Missed Annotations

Use this when a model/audit suggests missing annotations in existing dataset rows.

```bash
make audit-span-patches
make suggest-span-patches
make review-span-patches REVIEWER="$USER"
make apply-span-patches
make preview-promote-span-patches
make promote-span-patches
```

Convenience target:

```bash
make refresh-span-patches
```

Recommended target changes:

| Current target | Canonical target | Notes |
| --- | --- | --- |
| `audit-empty-training-docs` | `audit-span-patches` | Current name describes one implementation; canonical name describes the workflow object. |
| no separate target | `suggest-span-patches` | Optional split if audit preparation and model suggestion should be exposed separately. |
| `review-span-patches` | keep | Good. |
| `apply-span-patches` | keep | Good. |
| `span-patch-status` | `preview-promote-span-patches` | Align with preview naming. |
| `promote-span-patches` | keep | Good. |
| `refresh-span-patches` | keep | Good. |

If `audit-empty-training-docs` remains useful as a specific audit recipe, keep it as an alias or subtarget but do not make it the primary curator-facing workflow name.

### 4. Evaluation Disagreement Annotation

The current `legacy` naming should be removed from curator-facing targets. This is active HIPE-derived train/validation/test evaluation curation, not obsolete data.

Recommended canonical workflow:

```bash
make suggest-eval-disagreements CURATION_MODEL=...
make review-eval-disagreements REVIEWER="$USER"
make validate-eval-disagreements
make apply-eval-disagreements
```

Recommended target changes:

| Current target | Canonical target | Notes |
| --- | --- | --- |
| `curate-legacy-eval` | `suggest-eval-disagreements` | Runs evaluation and builds disagreement review queue. |
| `curate-legacy-validation` | `suggest-validation-disagreements` | Split-specific helper. |
| `curate-legacy-test` | `suggest-test-disagreements` | Split-specific helper. |
| `review-curation` | `review-eval-disagreements` | Specific object name. |
| `validate-curation` | `validate-eval-disagreements` | Specific object name. |
| `apply-curation` | `apply-eval-disagreements` | Specific object name. |
| `legacy-curation-state` | `eval-disagreement-state` | Avoid `legacy`. |

## State And Diagnostics Targets

State targets should describe what they summarize and should include all train/validation/test outputs.

Recommended canonical names:

| Current target | Canonical target | Notes |
| --- | --- | --- |
| `annotation-stats` | keep | Good curator-facing name. |
| `mention-profiles` | keep | Good. |
| `curation-dashboard` | `annotation-dashboard` | Optional; current name is acceptable. |
| `curation-state` | `annotation-state` | Optional broader rename. |
| `snippet-state` | `snippet-dataset-state` | Should count train + validation + test. |
| `dataset-state` | keep | Good. |
| `legacy-curation-state` | `eval-disagreement-state` | Avoid `legacy`. |
| `validate-dataset-splits` | keep | Good. |

Immediate consistency fix now applied:

- Update `lib.curation_state` and Makefile args so snippet state counts `train`, `validation`, and `test`, not only `train` and `test`.
- Rename printed columns from `exported` to `split_rows` or `split`, and from `entities` to `split_entities`.
- Rename `scored` to `suggested` in output, while the implementation may still read `*_SCORED_SNIPPETS` variables until configs are migrated.

Suggested display:

```text
family        sampled  suggested  reviewed  decisions  split_rows  split_entities  statuses
newsagency        52         52        52        126          14              16  ...
radio             20         20        20        463          17              26  ...
```

## File And Variable Naming

Make target names can change faster than file layout. Keep path changes conservative.

Recommended variable policy:

- Public Make help and docs use canonical names.
- Existing config variable names may remain temporarily if changing them creates too much churn.
- New variables should use canonical object names:
  - `NEWSAGENCY_SNIPPETS`
  - `RADIO_SNIPPETS` for new variables; keep `RADIOSTATION_*` as compatibility variables until a separate cleanup.
  - `SNIPPET_PROMOTE_*` is acceptable because promote is canonical.

Avoid renaming entity labels or metadata files:

- Keep `org.ent.radiostation.*`.
- Keep `resources/radiostation_seeds.json`.
- Keep `data/curated/snippets/radiostations/` unless doing a planned data-layout migration.

## Migration Plan

### Phase 1: Documentation And Help Text

- Update `Makefile help` and `help-review` to show only canonical names.
- Update `docs/curation.md` to use the canonical lifecycle.
- Add a short compatibility section listing old aliases.
- Update README examples that still use `score-*`, `export-*`, `merge-*`, or `legacy-*` curation names.

### Phase 2: Makefile Canonical Targets With Aliases

- Add canonical targets listed above.
- Keep old targets as aliases for one or two release cycles.
- Make aliases call canonical targets, not the other way around, so the canonical names own the command bodies.
- Keep MLM, training, evaluation, and publishing target names unchanged.

Example pattern:

```make
suggest-newsagency-snippet-spans:
	$(PYTHON) -m lib.score_newsagency_snippets ...

score-newsagency-snippets: suggest-newsagency-snippet-spans
```

### Phase 3: State Output Cleanup

- Fix snippet-state validation counting.
- Rename display columns to canonical lifecycle terms.
- Update JSON keys only if downstream scripts do not rely on them; otherwise add canonical keys and keep old keys for compatibility.

### Phase 4: Remove Or Hide Legacy Aliases

- Remove old names from `.PHONY`.
- Remove old names from help output.
- Keep only if there are shell scripts or external docs that still call them.

## Target Naming Checklist

Before adding a new annotation target, verify:

- Does the verb match exactly one lifecycle step?
- Does the object identify the material being worked on?
- Would an annotator understand the target without knowing the Python module?
- Does the target avoid implementation words like `score`, `merge`, or `export` unless those words are truly the user-facing operation?
- Is `promote` used for dataset integration?
- Is `apply` reserved for patching an existing split?
- Is `split` reserved for turning reviewed snippets into train/validation/test files?
- Are old aliases hidden from docs/help?
