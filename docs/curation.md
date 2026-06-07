# Curation Workflow

This document describes the curation workflows used to improve the Impresso media-source NER dataset. It covers three related but separate tasks:

1. **Audit and improve existing annotations.** Use audits to find missed spans, false positives, boundary problems, or label mistakes in data that is already part of the dataset.
2. **Add new snippets and annotate them.** Use Impresso search sampling to collect new short contexts for existing or newly scoped labels, then review the proposed spans before exporting them as additional training/test rows. This is the main **horizontal extension** path.
3. **Add new annotations to existing data items.** Use span-patch or targeted audit workflows to add another layer of annotation to documents that are already in the dataset, for example when adding a new entity family or repairing systematic false negatives. This is the main **vertical extension** path.

All workflows are model-assisted where possible: candidate spans are proposed by a model, seed-alias matching, or an audit query; a curator then accepts, rejects, modifies, or skips each candidate. Review decisions are append-only. Applying or promoting decisions writes revised JSONL data without editing the original evidence files in place.

Here, **HIPE-derived data** means the converted French/German news-agency annotations imported from earlier HIPE/CoNLL-style source files. This data is still part of the active training and evaluation base, but it is only one source of curation evidence. The current workbench also supports curation and sampling for English, plus side-language coverage for Luxembourgish and Italian. Some paths and command names keep `legacy-*` for compatibility with the existing workbench layout.

## Command Assumptions

The command examples below assume you run them from the repository root with the virtual environment activated:

```bash
source .venv/bin/activate
```

They also assume the default release config:

```
CFG ?= configs/model-v2.0.0.mk
```

For readability, examples omit repeated `PYTHON=.venv/bin/python` and `CFG=configs/model-v2.0.0.mk` overrides. Pass them only when you intentionally want a non-default interpreter or release config, for example:

```bash
make curation-state CFG=configs/model-v2.1.0.mk
```

Review targets require a `REVIEWER` override to tag decisions with the curator's identity. The examples use the shell variable `$USER`, which expands to your login name:

```bash
make review-newsagency-snippets REVIEWER="$USER"
```

You can substitute any short identifier instead of `$USER`.

## Dataset Extension Concepts

Curation changes the dataset in three ways:

- **Audit and correction** improves annotations that are already present, such as wrong boundaries, wrong labels, or false positives.
- **Horizontal extension** adds more documents or snippets for existing labels, languages, time periods, or newly scoped canonical entities. This includes the newer English coverage and side-language coverage for Luxembourgish and Italian, not only the original French/German HIPE-derived base.
- **Vertical extension** adds more annotation depth inside existing documents, such as missing spans, new labels, or future entity families.

Use sampled snippet review for horizontal extension. Use existing-span audits for audit and correction. Use audit-driven span patches for vertical extension and missed-annotation repair. For example, future newspaper annotation should usually proceed entity by entity, such as reviewing all likely `org.ent.newspaper.nzz` spans before moving to the next newspaper.

## From Evidence To Updated Dataset Splits

Most curation paths follow the same lifecycle:

```text
diagnostics/state
  -> sample or audit
  -> score or build candidates
  -> review decisions
  -> materialize reviewed decisions
  -> promote into the configured prerelease/source split
```

Use **promote** as the consistent name for the moment when reviewed changes become part of the dataset split used by training, export, and later publishing. Earlier steps only prepare local working artifacts: snippet review decisions are **exported** to standalone JSONL rows, while span-patch decisions are **applied** to a patched JSONL split. Those prepared artifacts are not integrated into the dataset until a `promote-*` or `refresh-*` target runs.

The `refresh-*` targets are convenience shortcuts that materialize reviewed decisions and then promote them:

- `refresh-span-patches` applies reviewed span-patch decisions, then promotes the patched split.
- `refresh-existing-spans` applies reviewed existing-span decisions, then promotes the patched split.
- `refresh-snippets` exports reviewed news-agency and radio-station snippets, then promotes the exported rows.

Promotion updates the configured local prerelease/source split that later feeds training, export, or publishing. It is separate from Hugging Face publishing.

## Which Curation Path Should I Use?

Start by choosing the path that matches the kind of dataset change you want to make.

| Situation                                                                    | Use this path                           | Main commands                                                                                                                           |
| ---------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| You want to inspect coverage, state, and mention surfaces before deciding.   | Diagnostics and state inspection        | `curation-dashboard` or individual state/statistics targets                                                                             |
| You want to audit already accepted annotations for boundary or label errors. | Existing-annotation audit               | `audit-existing-spans` -> `review-existing-spans` -> `refresh-existing-spans`                                                           |
| You want to add missed annotations to existing documents.                    | Vertical span-patch audit               | `audit-empty-training-docs` -> `review-span-patches` -> `refresh-span-patches`                                                          |
| You want new examples from Impresso search for news agencies.                | News-agency snippet curation            | `annotation-stats` -> `sample-needed-newsagencies` -> `score-newsagency-snippets` -> `review-newsagency-snippets` -> `refresh-snippets` |
| You want new examples from Impresso search for radio stations.               | Radio-station snippet curation          | `annotation-stats` -> `sample-radiostations` -> `score-radiostation-snippets` -> `review-radiostation-spans` -> `refresh-snippets`      |
| You want to clean the old HIPE-derived validation/test disagreement files.   | Legacy evaluation disagreement curation | `curate-legacy-eval` -> `review-curation` -> `validate-curation` -> `apply-curation`                                                    |

For new dataset growth, use the snippet paths for horizontal extension and the span-patch paths for vertical extension. Use the legacy evaluation path only when you are deliberately correcting gold-vs-model disagreements in the HIPE-derived validation or test folds.

Run `make help-review` when you only need the curation-related targets and common overrides. Run `make curation-dashboard` before a new session for a full read-only overview.

## Quick Recipes

### 0. Inspect current state

Use this before starting or resuming curation. It does not change data.

```bash
make curation-dashboard
```

`curation-dashboard` chains `annotation-stats`, `mention-profiles`, `curation-state`, `snippet-state`, `legacy-curation-state`, and `dataset-state` in sequence. Run individual targets when you only want one section:

```bash
make annotation-stats
make mention-profiles
make curation-state
make snippet-state
make legacy-curation-state
make dataset-state
```

### A. Audit existing annotations for one label

Use this audit path when a label is already present but may have inconsistent span boundaries or label assignments, for example whether `Agence Havas` or only `Havas` was selected.

```bash
make audit-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
make review-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas REVIEWER="$USER"
make refresh-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

Use this path one canonical label at a time. It is the safest way to normalize annotation style after a guideline decision.

### B. Add missed annotations to existing documents

Use this vertical-extension path when an audit has found likely false negatives, for example a missing agency or station in a document that already belongs to the training base.

```bash
make audit-empty-training-docs
make review-span-patches REVIEWER="$USER"
make refresh-span-patches
```

Use `accept` for a correct suggested span, `modify` for a correct entity with wrong boundary or label, `reject` for a verified false positive, and `skip` when the case needs later research.

### C. Add new news-agency snippets

Use this horizontal-extension path for more examples of existing agencies, language gaps, or newly added canonical agencies. The main coverage languages are German, French, and English; Luxembourgish and Italian are side languages with lower default targets.

```bash
make annotation-stats
make sample-needed-newsagencies
make score-newsagency-snippets
make review-newsagency-snippets REVIEWER="$USER"
make refresh-snippets
```

Use `sample-needed-newsagencies` for routine coverage work because it uses the label-language coverage report to focus on buckets below target. Use `sample-newsagencies` instead when you deliberately want unconstrained sampling or when no coverage report is available yet.

### D. Add new radio-station snippets

Use this horizontal-extension path for radio-station coverage across the same language setup.

```bash
make annotation-stats
make sample-radiostations RADIOSTATION_SAMPLE_ONLY_UNDER_TARGET=true
make score-radiostation-snippets
make review-radiostation-spans REVIEWER="$USER"
make refresh-snippets
```

Set `RADIOSTATION_SAMPLE_ONLY_UNDER_TARGET=true` for routine coverage work. Omit it when you intentionally want broader radio-station sampling.

### E. Correct HIPE-derived validation/test disagreements

Use this only for the older gold-vs-prediction disagreement workflow.

```bash
make curate-legacy-eval CURATION_MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1/best
make review-curation REVIEWER="$USER"
make validate-curation
make apply-curation
```

This path writes a non-destructive curated copy under `data/curated/legacy-import-curated/`. It is separate from snippet promotion and span-patch promotion.

## Path A: Audit Existing Annotations

Use an existing-span boundary audit when you want to select one agency or station label and systematically verify every already annotated occurrence. This is useful for checking whether boundaries consistently include words such as `agence`, or whether a label was applied too broadly.

Build the audit queue for one label:

```bash
make audit-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

Review with the same span-patch interface:

```bash
make review-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas REVIEWER="$USER"
```

Choice meanings in this audit mode are:

- `accept`: verify the existing span unchanged.
- `modify`: correct boundary and/or label with the token-based manual interface.
- `reject`: remove this existing annotation.
- `skip`: leave the occurrence unresolved.

Apply reviewed decisions to a local patched split:

```bash
make apply-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

This writes a local patched output file. It does not change the prerelease split yet. Inspect whether the patched output still differs from the configured promotion target:

```bash
make existing-span-status SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

Promote the patched output into the configured prerelease/source split, which is the file that feeds into training and export:

```bash
make promote-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

Promotion overwrites the configured source split with the patched version. The patched file also writes `changes.jsonl` and `changes.tsv` alongside it so you can review what changed before committing.

For the normal apply-and-promote sequence, use:

```bash
make refresh-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

`refresh-existing-spans` is the normal shortcut for applying and promoting in one step. Use `existing-span-status` beforehand if you want to confirm that there are pending changes worth promoting.

## Path B: Add Missed Annotations To Existing Documents

Use this vertical-extension path when an audit has found likely false negatives — documents that are already in the training base but are missing an annotation entirely.

Build or refresh the empty-training-doc audit. This runs the current classifier over training documents that have no gold entities and collects suspicious predicted spans:

```bash
make audit-empty-training-docs
```

Review suggested span patches:

```bash
make review-span-patches REVIEWER="$USER"
```

The review presents a concise suspicious-entity summary plus local context. Curator choices:

- `accept`: add the suggested span.
- `modify`: correct span offsets and/or label with the token-based manual interface.
- `reject`: mark the suggestion as a verified false positive.
- `skip`: leave it unresolved for a later pass.

Accepted, rejected, and modified decisions receive a local audit marker of the form `USER:DATE:verified`. Patch application also writes reviewer-neutral public `audit_marks` into the JSONL rows. Later audit queues suppress verified suggestions with the same span and label, so the same false positive or accepted correction is not repeatedly presented. Skipped decisions remain eligible for later review.

Apply accepted and corrected span decisions to a local patched split:

```bash
make apply-span-patches
```

This writes a local patched output first. It does not change the committed prerelease split yet. Inspect whether the patched output still differs from the configured promotion target:

```bash
make span-patch-status
```

Promote the patched output into the configured prerelease/source split:

```bash
make promote-span-patches
```

For the normal apply-and-promote sequence, use:

```bash
make refresh-span-patches
```

Decisions are append-only under `data/curated/span-patches/<audit-id>/decisions.jsonl`. Patch application writes a revised JSONL split plus `changes.jsonl`, `changes.tsv`, and `apply_summary.json`. Promotion copies the patched output into `SPAN_PATCH_PROMOTE_JSONL`, which defaults to `SPAN_PATCH_SOURCE_JSONL`.

The defaults point to the active v2.0.0 prerelease empty-training-doc audit. For target-scoped vertical extension, override `SPAN_PATCH_AUDIT_ID`, `SPAN_PATCH_CANDIDATES`, `SPAN_PATCH_SOURCE_JSONL`, and `SPAN_PATCH_TARGET_LABEL`.

## Path C/D: Add New Sampled Snippets

Snippet curation is the horizontal-extension path. News-agency and radio-station snippets share the same review/export/promotion logic; the main difference is how candidate spans are proposed and which metadata file supplies canonical labels.

Snippet review produces ignored working files under `data/curated/snippets/`. Exporting snippets converts accepted review decisions into train/test JSONL rows for each entity family:

```bash
make export-newsagency-snippets
make export-radiostation-snippets
```

The exported rows are not yet part of the training data. Promotion merges them into the configured prerelease/source split, which is the file that feeds into training and dataset export. Check what would be merged before committing:

```bash
make snippet-promotion-status
```

Promote the exported snippet rows into the prerelease/source split:

```bash
make promote-snippets
```

Promotion is idempotent by `document_id`: existing rows with the same ID are replaced, new rows are appended, and the destination split is sorted again. The prerelease split is the file you later publish or pass to the training pipeline.

For the normal export-and-promote sequence, use:

```bash
make refresh-snippets
```

`refresh-snippets` exports both reviewed news-agency and reviewed radio-station snippets before promotion. If only one family currently has reviewed rows, run the family-specific export target first and then promote separately, or make sure the other family's configured export file exists and is intentionally empty:

```bash
make export-newsagency-snippets
make promote-snippets
```

## Path E: Legacy Evaluation Disagreement Curation

This section documents the older gold-vs-prediction disagreement workflow for HIPE-derived validation and test folds. It is useful for correcting evaluation data, but it is not the main path for adding new sampled examples or repairing missed spans in training documents.

Run the selected model over the HIPE-derived validation and test folds:

```bash
make curate-legacy-eval CURATION_MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1/best
```

`curate-legacy-eval` includes both the HIPE-derived dev/validation fold and the HIPE-derived test fold. To curate only one fold, use:

```bash
make curate-legacy-validation CURATION_MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1/best

make curate-legacy-test CURATION_MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1/best
```

The review files are written below:

```text
data/curated/legacy-eval-curation/review/
```

Important files:

- `all_disagreements.jsonl`: complete disagreement set.
- `todo_disagreements.jsonl`: currently unresolved items to review.
- `decisions.jsonl`: append/update file for human review decisions.
- `validation_de_disagreements.jsonl`, `validation_fr_disagreements.jsonl`, `test_de_disagreements.jsonl`, `test_fr_disagreements.jsonl`: split/language views.

Each row has a deterministic `review_id`, document metadata, the gold span, the predicted span, token context, and any existing saved decision.

### Review In The Terminal

Review all pending items:

```bash
make review-curation REVIEWER="$USER"
```

For a short test session:

```bash
make review-curation REVIEWER="$USER" ARGS="--limit 20"
```

The review UI clears the screen for each example, highlights the target tokens, and shows numbered tokens only when requested with `N`.

Choices:

- `g`: accept the displayed gold span.
- `p`: accept the displayed prediction span.
- `b`: accept both displayed spans as valid mentions.
- `n`: neither displayed span is the final correct annotation; enter the correction in notes.
- `s`: ignore for this pass. Ignored items are audit records and do not block validation.
- `q`: quit without saving the current item.

Use notes for real corrections, especially boundary corrections. The apply step can parse notes such as:

```text
13:15 "Agence Wolff" label=org.ent.pressagency.wolff
```

### Validate Decisions

Validate that the current curation pass is internally consistent:

```bash
make validate-curation
```

`skip` decisions are treated as ignored for this pass and do not block completion. Use the stricter validator only when you intentionally want every disagreement resolved as a concrete correction:

```bash
make validate-curation ARGS="--require-complete"
```

For in-progress snapshots:

```bash
make validate-curation ARGS="--no-require-complete"
```

### Apply Decisions

Apply completed decisions to a new curated JSONL directory:

```bash
make apply-curation
```

This is non-destructive. It reads:

```text
data/curated/legacy-import/
```

and writes:

```text
data/curated/legacy-import-curated/
```

Output files:

- `train.jsonl`, `validation.jsonl`, `test.jsonl`: revised folds.
- `label_map.json`: copied label map.
- `curation_summary.json`: aggregate decision/application counts.
- `curation_changes.jsonl`: decision-level audit log.
- `curation_changes_tags.tsv`: lightweight CoNLL-like view with `TOKEN`, `BEFORE_NERTAG`, and `AFTER_NERTAG`.

Ignored decisions are recorded in the audit files and leave the corresponding annotation unchanged.

### Inspect Changes

Compare original and curated folds:

```bash
git diff --no-index data/curated/legacy-import/validation.jsonl data/curated/legacy-import-curated/validation.jsonl
git diff --no-index data/curated/legacy-import/test.jsonl data/curated/legacy-import-curated/test.jsonl
git diff --no-index data/curated/legacy-import/label_map.json data/curated/legacy-import-curated/label_map.json
```

For human review, prefer:

```text
data/curated/legacy-import-curated/curation_changes_tags.tsv
```

The TSV groups changes by review item and uses the HIPE `NoSpaceAfter` render metadata where available, so abbreviations and elisions appear in natural form such as `D.N.B.` or `l'Agence`.

## Snippet Details And Sampling Options

Sampled snippets use a lighter workflow than the HIPE-derived dev/test correction pass. Candidate rows should be JSONL and contain at least `id` plus either `text` or `snippet`. The tools also accept rows with `matches` and optional pre-tokenized `tokens`, `token_start_offsets`, and `token_end_offsets`.

The workflow still calls these short review units `snippets`, independent of which Impresso field produced the review text. Internally, sampling moved away from relying on the generic Impresso `snippet` field as the main annotation text. Those search-result previews are useful, but they can miss the highlighted query term or show a lead paragraph instead of the actual Solr hit context.

The default `NEWSAGENCY_SAMPLE_CONTEXT_SOURCE` and `RADIOSTATION_SAMPLE_CONTEXT_SOURCE` is now `full-content`. In that mode the sampler first uses the Solr `matches` fragment to identify the hit, then fetches the full Impresso content item, finds the highlighted match in the article text, and cuts a larger local context around it. `*_SAMPLE_CONTEXT_CHARS` controls the nominal maximum character radius; the default `256` is a practical guess for staying near 128 subtokens in typical review examples. The total context around the match is randomly shortened, but kept at least 100 characters when the article has enough text, and the amount before the match is varied using the sampler seed. This prevents the target mention from always being centered or followed by a fixed-length right context. The original `snippet`, raw `matches`, `match_html`, and cleaned `match_text` are kept as provenance fields.

When API/content fetches are too slow or unavailable, use `NEWSAGENCY_SAMPLE_CONTEXT_SOURCE=match` or `RADIOSTATION_SAMPLE_CONTEXT_SOURCE=match`. That lightweight mode turns each Solr `matches` fragment into its own snippet row and strips the `<em>...</em>` markup, but the resulting snippets can be short or truncated because they are only search-hit fragments.

### News-Agency Snippets

Use real Impresso search snippets for new curation. Bootstrap snippets built from HIPE-derived JSONL are useful for testing the scoring/review/export workflow, but they are not new evidence. The parent sampler file `../newsagencies_by_article.json` maps agency names to article IDs only and must be combined with an Impresso API fetch before it can produce candidate snippets.

Sample real Impresso search snippets:

```bash
make sample-newsagencies NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG=5 NEWSAGENCY_SAMPLE_MAX_PER_LABEL=5 NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL=3
```

For routine coverage-driven sampling, first update coverage statistics and then sample only buckets below target:

```bash
make annotation-stats
make sample-needed-newsagencies
```

This writes `data/candidates/newsagency_search_snippets.jsonl` by default. Query strings are derived from the trainable labels in `resources/newsagency_seeds.json`, including multilingual aliases. Sampling keeps an append-only issue/entity registry at `data/candidates/sample_entity_pairs.jsonl` by default and skips later results from newspaper issues already sampled for the same canonical label. The default per-round cap is intentionally small: at most five selected samples per entity.

Build a local bootstrap snippet file from the curated HIPE-derived JSONL only when you explicitly want test material from the baseline HIPE-derived folds:

```bash
make build-newsagency-snippets-from-legacy
```

This writes `data/candidates/newsagency_legacy_snippets.jsonl` by default.

Score sampled snippets with the current model:

```bash
make score-newsagency-snippets NEWSAGENCY_SNIPPETS=data/candidates/newsagency_search_snippets.jsonl HF_MODEL=impresso-project/mmbert-impresso-mediasources-ner
```

The scorer writes `data/curated/snippets/newsagencies/scored.jsonl` by default. Rows are marked:

- `auto_accepted`: high-confidence prediction matching the candidate agency label. Multi-span snippets are also auto-accepted when every predicted agency span is very confident; those spans are stored explicitly for export.
- `needs_review`: no prediction, low confidence, low margin, label mismatch, uncertain multiple spans, or suspicious boundary.

By default, `AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE` inherits `AUTO_ACCEPT_MIN_CONFIDENCE`, so `AUTO_ACCEPT_MIN_CONFIDENCE=0.95` applies to both single-span and multi-span snippets unless the multi-span threshold is explicitly overridden.

Review uncertain rows:

```bash
make review-newsagency-snippets REVIEWER="$USER"
```

Choices are accept/review prediction spans, enter a manual token span, reject a suggested annotation, remove a bad sample, skip temporarily, or show info. If several agencies are predicted in the same snippet, choosing `a` reviews them one after another so multiple spans can be accepted in one decision. During per-span review, `a` accepts the predicted span and predicted label. If the boundary is correct but the label should be the candidate label, use `c`; for example, in `Telegraphen-Union berichtet:`, keep `Telegraphen-Union` as `org.ent.pressagency.telegraphen-union` and reject `berichtet`. In manual mode, the numbered tokens are shown automatically and you can add several spans before saving. You can type an explicit span with a full label or canonical id, such as `12:13 org.ent.pressagency.reuters` or `12:13 reuters`. You can also paste the numbered tokens themselves, for example `9:B 10:. 11:B 12:. 13:C 14:. bbc` or `33:Radio 34:. agence-radio`; the review tool infers the contiguous token range, resolves the canonical id to the full label, and prints an `interpreted:` line with the final span and label. If no label is supplied, the tool uses the current candidate label when one is available. Press `i` to print the current review input file, the local label metadata from `resources/newsagency_seeds.json` and `resources/radiostation_seeds.json`, the agency description, active period, multilingual aliases, annotation notes, contextual aliases, source links, the source file when known, and a direct Impresso article URL such as `https://impresso-project.ch/app/article/ARTICLEID` when the source document ID is known. Decisions are append-only in `data/curated/snippets/newsagencies/decisions.jsonl`, and the reviewed rows are materialized to `data/curated/snippets/newsagencies/reviewed.jsonl`.

Decision semantics:

- `a` or `m`: accept one or more spans; accepted rows can be exported to training JSONL.
- `r`: reject the suggested annotation/spans for this item; the sample is final but contributes no training row.
- `s`: skip temporarily; the sample remains pending and will be shown again in a later review run.
- `R`: remove the sample permanently from review/export because the snippet itself is unusable or irrelevant.

The review target defaults to 20 items per run. Override with `REVIEW_MAX_ITEMS=...` when you want a shorter or longer batch.

Export accepted rows into training JSONL:

```bash
make export-newsagency-snippets
```

The default outputs are `data/curated/snippets/newsagencies/train.jsonl` and `data/curated/snippets/newsagencies/test.jsonl`. They use the same token-label/entity schema as the HIPE-derived dataset and preserve `source_component` so snippet-derived examples can be mixed deterministically later. The split is deterministic and grouped by source issue/document so snippets from the same source issue do not leak across train and test. Override the holdout size with `SNIPPET_TEST_FRACTION=...`.

Use `refresh-snippets` when the reviewed snippet rows are ready to be exported and promoted into the configured prerelease/source split.

`data/curated/` is a local working area. When reviewed snippets are ready to become shared project state, include the resulting full dataset snapshot in `data/releases/<dataset-version>/` before cleaning local state or publishing a new Hugging Face dataset revision.

Useful overrides:

- `AUTO_ACCEPT_MIN_CONFIDENCE=0.95`
- `AUTO_ACCEPT_MIN_MARGIN=0.30`
- `REVIEW_MAX_ITEMS=20`

### Language-Aware Coverage Targets

`make annotation-stats` writes label-level and label-language coverage to `data/curated/annotation_coverage.json`. Targeted sampling and review prioritization use the label-language buckets, so a label with many German examples can still be sampled and reviewed for French, English, Luxembourgish, or Italian gaps. The original HIPE-derived base is French/German, but the current curation target is broader.

Default coverage targets are:

- Main languages `de fr en`: 20 accepted examples per label and language.
- Side languages `lb it`: 5 accepted examples per label and language.

Configure these with:

```bash
make annotation-stats ANNOTATION_MAIN_LANGS="de fr en" ANNOTATION_SIDE_LANGS="lb it" ANNOTATION_MAIN_TARGET_PER_LABEL_LANG=20 ANNOTATION_SIDE_TARGET_PER_LABEL_LANG=5
```

Use `ANNOTATION_LANGUAGE_TARGETS` for explicit per-language overrides, for example:

```bash
make annotation-stats ANNOTATION_LANGUAGE_TARGETS="de=30 fr=30 en=20 lb=8 it=8"
```

### Entity Mention Profiles

Use empirical mention profiles to inspect how each label is actually annotated in the current dataset snapshot:

```bash
make mention-profiles
```

The default outputs are:

- `reports.d/entity-mention-profiles/profiles.md`
- `reports.d/entity-mention-profiles/profiles.json`
- `reports.d/entity-mention-profiles/surfaces.tsv`

These files are generated local evidence. They answer questions such as whether `Agence Havas` or just `Havas` is usually selected, which languages use which surface forms, and whether generic terms such as `agence`, `agency`, `Agentur`, or `radio` are commonly included in the accepted span.

When a pattern becomes annotation guidance rather than just evidence, copy the distilled rule into the relevant row in `resources/newsagency_seeds.json` or `resources/radiostation_seeds.json`:

```json
"mention_profile": {
  "typical_surfaces": ["Havas", "Agence Havas", "(Havas.)"],
  "span_guidance": "Annotate Havas alone in source formulas. Include Agence when the visible phrase is Agence Havas.",
  "include_generic_terms": "when part of the agency name",
  "exclude_patterns": ["generic agence without resolvable agency"]
}
```

The `i` info view in review and audit review displays this `mention_profile` field next to the existing label metadata.

### Radio-Station Snippets

The default radio-station input is sampled into `data/candidates/radiostation_search_snippets.jsonl` with `make sample-radiostations`. For routine coverage-driven sampling, run `make annotation-stats` first and pass `RADIOSTATION_SAMPLE_ONLY_UNDER_TARGET=true`.

```bash
make annotation-stats
make sample-radiostations RADIOSTATION_SAMPLE_ONLY_UNDER_TARGET=true
```

Because the current NER model was trained from HIPE-derived news-agency annotations and the current baseline label map does not contain radio-station labels yet, radio-station scoring combines two sources of span suggestions: deterministic radio-station seed-alias matching and the current NER model's media-agency predictions. This means a search hit sampled for `BBC` can still show a `Reuter` or `Havas` model prediction if the actual snippet contains that agency instead of the searched radio-station mention.

Score sampled radio-station snippets:

```bash
make score-radiostation-snippets
```

Review suggested radio-station spans:

```bash
make review-radiostation-spans REVIEWER="$USER"
```

Export accepted radio-station spans:

```bash
make export-radiostation-snippets
```

This writes `data/curated/snippets/radiostations/train.jsonl` and `data/curated/snippets/radiostations/test.jsonl`. The exporter extends the baseline HIPE-derived label map in memory with labels from `resources/radiostation_seeds.json`, so radio-station rows can be prepared before retraining a model with radio labels. The split is deterministic and grouped by source issue/document.

Use `refresh-snippets` when the reviewed radio-station rows are ready to be exported and promoted into the configured prerelease/source split.

Radio-station snippets use the same span-review model as news-agency snippets. Rows with no acceptable radio-station span should be rejected or skipped in `review-radiostation-spans`; those decisions remain audit evidence in `data/curated/snippets/radiostations/reviewed.jsonl`, but they do not produce positive token-classification rows.

Before sharing a dataset extension, copy or generate the full release snapshot under `data/releases/<dataset-version>/`. Ignored local review files under `data/curated/` are not preserved by `make clean`.
