# Curation Workflow

This document describes the curation workflows used to improve the Impresso media-source NER dataset. It covers three related but separate tasks:

1. **Audit and improve existing annotations.** Use audits to find missed spans, false positives, boundary problems, or label mistakes in data that is already part of the dataset.
2. **Add new snippets and annotate them.** Use Impresso search sampling to collect new short contexts for existing or newly scoped labels, then review the proposed spans before splitting them as additional train/validation/test rows. This is the main **horizontal extension** path.
3. **Add new annotations to existing data items.** Use span-patch or targeted audit workflows to add another layer of annotation to documents that are already in the dataset, for example when adding a new entity family or repairing systematic false negatives. This is the main **vertical extension** path.

All workflows are model-assisted where possible: candidate spans are proposed by a model, seed-alias matching, or an audit query; a curator then accepts, rejects, modifies, or skips each candidate. Review decisions are append-only. Applying or promoting decisions writes revised JSONL data without editing the original evidence files in place.

Here, **HIPE-derived data** means the converted French/German news-agency annotations imported from earlier HIPE/CoNLL-style source files. This data is still part of the active training and evaluation base, but it is only one source of curation evidence. The current workbench also supports curation and sampling for English, plus side-language coverage for Luxembourgish and Italian.

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
make review-newsagency-snippet-spans REVIEWER="$USER"
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
  -> suggest spans
  -> review decisions
  -> split or apply reviewed decisions
  -> preview promotion
  -> promote into the configured prerelease/source split
```

Read the activity names as curator actions:

- **Inspect** the current state before changing anything: coverage, mention profiles, split health, and pending review queues.
- **Sample** new snippets from outside the dataset when you need more examples for a label, language, time period, or entity family.
- **Audit** existing dataset rows when you suspect missing spans, wrong labels, bad boundaries, or false positives.
- **Suggest** candidate spans automatically with a model, seed-alias matching, or an audit query; suggestions are not gold annotations yet.
- **Review** the suggestions manually and decide whether to accept, correct, reject, remove, or skip each item.
- **Split** reviewed snippet decisions into train/validation/test JSONL files; this prepares new standalone rows but does not update the dataset yet.
- **Apply** reviewed patch decisions to existing dataset rows; this prepares a patched split but does not update the dataset yet.
- **Preview promotion** before integration when you want to see what would be added, replaced, removed, or blocked.
- **Promote** prepared rows or patched splits into the configured prerelease/source dataset used by training, export, and publishing.
- **Integrate snippets** when you want the post-review shortcut that splits reviewed snippet decisions, previews promotion, and then promotes the result.
Use **promote** as the consistent name for the moment when reviewed changes become part of the dataset split used by training, export, and later publishing. Earlier steps only prepare local working artifacts: snippet review decisions are **split** into standalone JSONL rows, while span-patch decisions are **applied** to a patched JSONL split. Those prepared artifacts are not integrated into the dataset until a `promote-*` or `integrate-*` target runs.

The post-review shortcut targets materialize reviewed decisions and then promote them:

- `integrate-snippets` splits reviewed news-agency and radio snippets, previews promotion, then promotes the split rows into the dataset.
- `integrate-span-patches` applies reviewed span-patch decisions, then promotes the patched split.
- `integrate-existing-spans` applies reviewed existing-span decisions, then promotes the patched split.

Promotion updates the configured local prerelease/source split that later feeds training, export, or publishing. It is separate from Hugging Face publishing.

## Which Curation Path Should I Use?

Start by choosing the path that matches the kind of dataset change you want to make.

| Situation                                                                    | Use this path                           | Main commands                                                                                                                           |
| ---------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| You want to inspect coverage, state, and mention surfaces before deciding.   | Diagnostics and state inspection        | `curation-dashboard` or individual state/statistics targets                                                                             |
| You want to audit already accepted annotations for boundary or label errors. | Existing-annotation audit               | `audit-existing-spans` -> `review-existing-spans` -> `integrate-existing-spans`                                                          |
| You want to add missed annotations to existing documents for one entity.     | Target-specific missing-span audit      | `audit-missing-spans` -> `review-missing-spans` -> `integrate-missing-spans`                                                             |
| You want to inspect empty-gold training documents for broad false negatives. | Empty-document span-patch audit         | `audit-empty-training-docs` -> `review-span-patches` -> `integrate-span-patches`                                                         |
| You want new examples from Impresso search for news agencies.                | News-agency snippet curation            | `annotation-stats` -> `sample-newsagency-snippets` -> `suggest-newsagency-snippet-spans` -> `review-newsagency-snippet-spans` -> `integrate-snippets` |
| You want new examples from Impresso search for radio stations.               | Radio snippet curation                  | `annotation-stats` -> `sample-radio-snippets` -> `suggest-radio-snippet-spans` -> `review-radio-snippet-spans` -> `integrate-snippets`      |
| You want to clean HIPE-derived gold-vs-prediction disagreement files.       | Evaluation disagreement curation        | `suggest-eval-disagreements` -> `review-curation` -> `validate-curation` -> `apply-curation`                                             |

For new dataset growth, use the snippet paths for horizontal extension and the span-patch paths for vertical extension. Use the evaluation disagreement path only when you are deliberately correcting gold-vs-model disagreements in the configured train/validation/test folds.

Run `make help-annotation` when you only need the curation-related targets and common overrides. Run `make curation-dashboard` before a new session for a full read-only overview.

## Quick Recipes

### 0. Inspect current state

Use this before starting or resuming curation. It does not change data.

```bash
make curation-dashboard
```

`curation-dashboard` chains `annotation-stats`, `mention-profiles`, `curation-state`, `snippet-state`, `eval-disagreement-state`, and `dataset-state` in sequence. Run individual targets when you only want one section:

```bash
make annotation-stats
make mention-profiles
make curation-state
make snippet-state
make eval-disagreement-state
make dataset-state
```

### A. Audit existing annotations for one label

Use this audit path when a label is already present but may have inconsistent span boundaries or label assignments, for example whether `Agence Havas` or only `Havas` was selected.

```bash
make audit-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
make review-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas REVIEWER="$USER"
make integrate-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

Use this path one canonical label at a time. It is the safest way to normalize annotation style after a guideline decision.

### B. Add missed annotations to existing documents

Use the target-specific vertical-extension path when you want to scan an existing split for one entity, for example possible missed `org.ent.pressagency.ata` mentions in train, validation, or test. The audit uses high-precision metadata patterns by default. If model prediction files exist from `suggest-eval-disagreements-*`, it also includes current-model suggestions for the target label.

```bash
make audit-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train
make review-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train REVIEWER="$USER"
make integrate-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train
```

Use `MISSING_SPAN_SPLIT=validation` or `MISSING_SPAN_SPLIT=test` to audit those configured splits instead. The audit output, decisions, patched split, and change logs are namespaced by label and split.

To include current-model suggestions, run the split-specific evaluation first:

```bash
make suggest-eval-disagreements-validation
make audit-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=validation
```

Use `ARGS="--no-model"` when you want pattern-only suggestions, or `ARGS="--no-patterns"` when you want model-only suggestions from an existing prediction file.

Use the broader empty-document audit when you want to inspect likely false negatives in empty-gold training rows without selecting a specific entity first:

```bash
make audit-empty-training-docs
make review-span-patches REVIEWER="$USER"
make integrate-span-patches
```

Use `accept` for a correct suggested span, `modify` for a correct entity with wrong boundary or label, `reject` for a verified false positive, and `skip` when the case needs later research.

### C. Add new news-agency snippets

Use this horizontal-extension path for more examples of existing agencies, language gaps, or newly added canonical agencies. The main coverage languages are German, French, and English; Luxembourgish and Italian are side languages with lower default targets.

Run the human-in-the-loop cycle step by step:

```bash
make annotation-stats
make sample-newsagency-snippets
make suggest-newsagency-snippet-spans
make review-newsagency-snippet-spans REVIEWER="$USER"
make integrate-snippets
```

Use `sample-newsagency-snippets` for routine coverage work because it uses the label-language coverage report to focus on buckets below target. Use `sample-freely-newsagency-snippets` instead when you deliberately want unconstrained sampling or when no coverage report is available yet.

### D. Add new radio-station snippets

Use this horizontal-extension path for radio-station coverage across the same language setup.

Run the human-in-the-loop cycle step by step:

```bash
make annotation-stats
make sample-radio-snippets
make suggest-radio-snippet-spans
make review-radio-snippet-spans REVIEWER="$USER"
make integrate-snippets
```

Use `sample-radio-snippets` for routine coverage work because it uses the label-language coverage report to focus on buckets below target. Use `sample-freely-radio-snippets` instead when you deliberately want broader radio-station sampling or when no coverage report is available yet.

### E. Correct HIPE-derived train/validation/test disagreements

Use this only for the gold-vs-prediction disagreement workflow over existing configured splits.

```bash
make suggest-eval-disagreements
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
make integrate-existing-spans SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas
```

`integrate-existing-spans` is the normal shortcut for applying and promoting in one step. Use `existing-span-status` beforehand if you want to confirm that there are pending changes worth promoting.

## Path B: Add Missed Annotations To Existing Documents

Use this vertical-extension path when an audit has found likely false negatives — documents that are already in the training base but are missing an annotation entirely.

For routine entity-by-entity repair, build a target-specific missing-span queue. This scans one configured split and suggests spans for one canonical label when the current model and/or metadata patterns find a mention that does not overlap an existing annotation:

```bash
make audit-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train
```

Review the target-specific suggestions:

```bash
make review-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train REVIEWER="$USER"
```

The review presents a concise suspicious-entity summary plus local context. Curator choices:

- `accept`: add the suggested span.
- `modify`: correct span offsets and/or label with the token-based manual interface.
- `reject`: mark the suggestion as a verified false positive.
- `skip`: leave it unresolved for a later pass.

Accepted, rejected, and modified decisions receive a local audit marker of the form `USER:DATE:verified`. Patch application also writes reviewer-neutral public `audit_marks` into the JSONL rows. Later audit queues suppress verified suggestions with the same span and label, so the same false positive or accepted correction is not repeatedly presented. Skipped decisions remain eligible for later review.

Apply accepted and corrected span decisions to a local patched split:

```bash
make apply-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train
```

This writes a local patched output first. It does not change the committed prerelease split yet. Inspect whether the patched output still differs from the configured promotion target:

```bash
make missing-span-status MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train
```

Promote the patched output into the configured prerelease/source split:

```bash
make promote-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train
```

For the normal apply-and-promote sequence, use:

```bash
make integrate-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata MISSING_SPAN_SPLIT=train
```

Decisions are append-only under `data/curated/span-patches/<audit-id>/decisions.jsonl`. Patch application writes a revised JSONL split plus `changes.jsonl`, `changes.tsv`, and `apply_summary.json`. Promotion copies the patched output into `MISSING_SPAN_PROMOTE_JSONL`, which defaults to the selected source split.

Use `MISSING_SPAN_SPLIT=validation` or `MISSING_SPAN_SPLIT=test` for those configured splits. To include model suggestions, generate predictions for that split first with `suggest-eval-disagreements-train`, `suggest-eval-disagreements-validation`, or `suggest-eval-disagreements-test`. The audit uses pattern suggestions even when no prediction file exists. Use `ARGS="--no-model"` for pattern-only review, or `ARGS="--no-patterns"` for model-only review.

The broader empty-training-doc audit is still useful when you want an unscoped false-negative scan over empty-gold training rows:

```bash
make audit-empty-training-docs
make review-span-patches REVIEWER="$USER"
make integrate-span-patches
```

Those defaults point to the active v2.0.0 prerelease empty-training-doc audit. For custom broad span-patch audits, override `SPAN_PATCH_AUDIT_ID`, `SPAN_PATCH_CANDIDATES`, `SPAN_PATCH_SOURCE_JSONL`, and `SPAN_PATCH_TARGET_LABEL`.

## Path C/D: Add New Sampled Snippets

Snippet curation is the horizontal-extension path. News-agency and radio snippets share the same review, split, and promote logic; the main difference is how candidate spans are proposed and which metadata file supplies canonical labels.

Snippet review produces ignored working files under `data/curated/snippets/`. Splitting snippets converts accepted review decisions into train/validation/test JSONL rows for each entity family:

```bash
make split-newsagency-snippets
make split-radio-snippets
```

The split rows are not yet part of the training data. Promotion integrates them into the configured prerelease/source split, which is the file that feeds into training and dataset export. Check what would be promoted before committing:

```bash
make preview-promote-snippets
```

Promote the split snippet rows into the prerelease/source split:

```bash
make promote-snippets
```

Promotion is idempotent by `document_id`: existing rows with the same ID are replaced, new rows are appended, and the destination split is sorted again. The prerelease split is the file you later publish or pass to the training pipeline.

For the normal split-preview-promote sequence, use:

```bash
make integrate-snippets
```

`integrate-snippets` splits both reviewed news-agency and reviewed radio snippets, previews promotion, and then promotes. If only one family currently has reviewed rows, run the family-specific split target first and then promote separately, or make sure the other family's configured split files exist and are intentionally empty:

```bash
make split-newsagency-snippets
make preview-promote-snippets
make promote-snippets
```

## Path E: Evaluation Disagreement Curation

This section documents the gold-vs-prediction disagreement workflow for HIPE-derived train/validation/test folds. It is useful for correcting existing dataset rows, but it is not the main path for adding new sampled examples or repairing missed spans in training documents.

Run the selected model over the configured train/validation/test folds:

```bash
make suggest-eval-disagreements
```

For the v2 config, this uses the configured v2 model and its own saved `label_map.json`. If the v2 model has not been trained yet, run `make train` first.

`suggest-eval-disagreements` includes the configured train, validation, and test folds. To curate only one fold, use:

```bash
make suggest-eval-disagreements-validation

make suggest-eval-disagreements-test
```

For a custom checker checkpoint, pass the matching label map as well, for example `CURATION_MODEL=models.d/my-checkpoint/best CURATION_LABEL_MAP=models.d/my-checkpoint/best/label_map.json`.

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
- `m`: enter manual annotation span(s) with the token-based manual interface.
- `n`: neither displayed span is a valid mention.
- `s`: ignore for this pass. Ignored items are audit records and do not block validation.
- `q`: quit without saving the current item.

Use `m` for real corrections, especially boundary or label corrections. The reviewer prints numbered tokens and accepts the same style as the snippet/span-patch interfaces:

```text
13:15 org.ent.pressagency.wolff
13:Agence 14:Wolff wolff
```

Manual corrections are stored as structured token spans in `accepted_spans`. Notes are for comments, not for encoding the final annotation.

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

For routine gap filling, sample real Impresso search snippets from label/language buckets below target:

```bash
make annotation-stats
make sample-newsagency-snippets NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG=5 NEWSAGENCY_SAMPLE_MAX_PER_LABEL=5 NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL=3
```

For deliberately unconstrained sampling, use the explicit free-sampling target:

```bash
make sample-freely-newsagency-snippets NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG=5 NEWSAGENCY_SAMPLE_MAX_PER_LABEL=5 NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL=3
```

To focus the under-target sampling pass on a specific news agency, pass the full canonical label through `ARGS`:

```bash
make sample-newsagency-snippets ARGS="--labels org.ent.pressagency.reuters"
```

Multiple news-agency labels can be whitespace-separated inside the `--labels` value. `sample-newsagency-snippets` uses the intersection of `--labels` and the labels that are still below target in the coverage report. Use `sample-freely-newsagency-snippets ARGS="--labels ..."` when you want to sample a specific label without the under-target coverage filter.

This writes `data/candidates/newsagency_search_snippets.jsonl` by default. Query strings are derived from the trainable labels in `resources/newsagency_seeds.json`, including multilingual aliases. Sampling keeps an append-only issue/entity registry at `data/candidates/sample_entity_pairs.jsonl` by default and skips later results from newspaper issues already sampled for the same canonical label. The default per-round cap is intentionally small: at most five selected samples per entity.

Suggest spans for sampled snippets. The suggest step uses the configured model plus known-entity metadata matchers across the configured news-agency, radio-station, and optional newspaper catalogs. This means a news-agency sample can still be preannotated with radio-station or newspaper spans when those known entities occur in the same snippet:

```bash
make suggest-newsagency-snippet-spans NEWSAGENCY_SNIPPETS=data/candidates/newsagency_search_snippets.jsonl HF_MODEL=impresso-project/mmbert-impresso-mediasources-ner
```

The scorer writes `data/curated/snippets/newsagencies/scored.jsonl` by default. Rows are marked:

- `auto_accepted`: high-confidence prediction matching the candidate agency label. Multi-span snippets are also auto-accepted when every predicted agency span is very confident; those spans are stored explicitly for export.
- `needs_review`: no prediction, low confidence, low margin, label mismatch, uncertain multiple spans, or suspicious boundary.

By default, `AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE` inherits `AUTO_ACCEPT_MIN_CONFIDENCE`, so `AUTO_ACCEPT_MIN_CONFIDENCE=0.95` applies to both single-span and multi-span snippets unless the multi-span threshold is explicitly overridden.

Review uncertain rows:

```bash
make review-newsagency-snippet-spans REVIEWER="$USER"
```

Choices are accept/review prediction spans, enter a manual token span, reject a suggested annotation, remove a bad sample, skip temporarily, or show info. If several agencies are predicted in the same snippet, choosing `a` reviews them one after another so multiple spans can be accepted in one decision. During per-span review, `a` accepts the predicted span and predicted label. If the boundary is correct but the label should be the candidate label, use `c`; for example, in `Telegraphen-Union berichtet:`, keep `Telegraphen-Union` as `org.ent.pressagency.telegraphen-union` and reject `berichtet`. In manual mode, the numbered tokens are shown automatically and you can add several spans before saving. You can type an explicit span with a full label or canonical id, such as `12:13 org.ent.pressagency.reuters` or `12:13 reuters`. You can also paste the numbered tokens themselves, for example `9:B 10:. 11:B 12:. 13:C 14:. bbc` or `33:Radio 34:. agence-radio`; the review tool infers the contiguous token range, resolves the canonical id to the full label, and prints an `interpreted:` line with the final span and label. If no label is supplied, the tool uses the current candidate label when one is available. Press `i` to print the current review input file, the local label metadata from `resources/newsagency_seeds.json` and `resources/radiostation_seeds.json`, the agency description, active period, multilingual aliases, annotation notes, contextual aliases, source links, the source file when known, and a direct Impresso article URL such as `https://impresso-project.ch/app/article/ARTICLEID` when the source document ID is known. Decisions are append-only in `data/curated/snippets/newsagencies/decisions.jsonl`, and the reviewed rows are materialized to `data/curated/snippets/newsagencies/reviewed.jsonl`.

Decision semantics:

- `a` or `m`: accept one or more spans; accepted rows can be split into train/validation/test JSONL.
- `r`: reject the suggested annotation/spans for this item; the sample is final but contributes no training row.
- `s`: skip temporarily; the sample remains pending and will be shown again in a later review run.
- `R`: remove the sample permanently from review/export because the snippet itself is unusable or irrelevant.

The review target defaults to 20 items per run. Override with `REVIEW_MAX_ITEMS=...` when you want a shorter or longer batch.

Split accepted rows into train/validation/test JSONL:

```bash
make split-newsagency-snippets
```

The default outputs are `data/curated/snippets/newsagencies/train.jsonl`, `data/curated/snippets/newsagencies/validation.jsonl`, and `data/curated/snippets/newsagencies/test.jsonl`. They use the compact v2 token-label/entity schema: integer label IDs are derived later from `label_map.json`, and public entity rows do not carry synthetic entity IDs or normalization compatibility fields. The default policy is 80/10/10 train/validation/test, with deterministic grouping by source issue/document so snippets from the same source issue do not leak across splits. Override the holdout sizes with `SNIPPET_VALIDATION_FRACTION=...` and `SNIPPET_TEST_FRACTION=...`.

Use `integrate-snippets` when the reviewed snippet rows are ready to be split, previewed, and promoted into the configured prerelease/source split.

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

The default radio-station input is sampled into `data/candidates/radiostation_search_snippets.jsonl` with `make sample-radio-snippets`. This is the routine coverage-driven target: run `make annotation-stats` first so it can focus on label/language buckets below target.

```bash
make annotation-stats
make sample-radio-snippets
```

To focus the under-target sampling pass on a specific radio station, pass the full canonical label through `ARGS`:

```bash
make sample-radio-snippets ARGS="--labels org.ent.radiostation.rtl"
```

Multiple radio-station labels can be whitespace-separated inside the `--labels` value. `sample-radio-snippets` uses the intersection of `--labels` and the labels that are still below target in the coverage report. Use `sample-freely-radio-snippets ARGS="--labels ..."` when you want to sample a specific label without the under-target coverage filter, or use `sample-freely-radio-snippets` without labels when you deliberately want broader radio-station sampling.

Because the model can only predict labels it has already been trained on, snippet suggestion combines the current NER model with deterministic metadata matchers for known media-source labels. This means a search hit sampled for `BBC` can still show a `Reuter` or `Havas` span if the actual snippet contains that agency instead of, or in addition to, the searched radio-station mention.

Suggest spans for sampled radio snippets:

```bash
make suggest-radio-snippet-spans
```

Review suggested radio-station spans:

```bash
make review-radio-snippet-spans REVIEWER="$USER"
```

Split accepted radio spans into train/validation/test JSONL:

```bash
make split-radio-snippets
```

This writes `data/curated/snippets/radiostations/train.jsonl`, `data/curated/snippets/radiostations/validation.jsonl`, and `data/curated/snippets/radiostations/test.jsonl`. The exporter extends the baseline HIPE-derived label map in memory with labels from `resources/radiostation_seeds.json`, so radio-station rows can be prepared before retraining a model with radio labels. The default policy is 80/10/10 train/validation/test, with deterministic grouping by source issue/document.

Use `integrate-snippets` when the reviewed radio rows are ready to be split, previewed, and promoted into the configured prerelease/source split.

Radio-station snippets use the same span-review model as news-agency snippets. Rows with no acceptable radio-station span should be rejected or skipped in `review-radio-snippet-spans`; those decisions remain audit evidence in `data/curated/snippets/radiostations/reviewed.jsonl`, but they do not produce positive token-classification rows.

Before sharing a dataset extension, copy or generate the full release snapshot under `data/releases/<dataset-version>/`. Ignored local review files under `data/curated/` are not preserved by `make clean`.
