# Curation Workflow

This document describes how to review and apply corrections for the HIPE-derived French/German dev and test folds.

The current workflow is model-assisted: run the trained model on the HIPE-derived validation/test data, build gold-vs-prediction disagreement records, review those records in the terminal, validate the decisions, and then write a non-destructive curated JSONL copy.

Here, **HIPE-derived data** means the converted French/German news-agency annotations imported from earlier HIPE/CoNLL-style source files. This data is still part of the active training and evaluation base. Some paths and command names keep `legacy-*` for compatibility with the existing workbench layout.

## Dataset Extension Modes

There are two extension modes:

- **Horizontal extension** adds more documents or snippets for existing labels.
- **Vertical extension** adds more annotation depth or new entity families inside existing documents.

Use sampled snippet review for horizontal extension. Use audit-driven span patches for vertical extension and missed-annotation repair. For example, future newspaper annotation should usually proceed entity by entity, such as reviewing all likely `org.ent.newspaper.nzz` spans before moving to the next newspaper.

## Audit-Driven Span Patches

Span patches start from an audit file that already contains suspicious candidate spans. The empty-training-doc audit is the first concrete use case: run the current classifier on documents with no gold entities, then review only documents where the classifier predicts a missing mention.

Build or refresh the audit:

```bash
make audit-empty-training-docs \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk
```

Review suggested span patches:

```bash
make review-span-patches \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  REVIEWER="$USER"
```

The review presents a concise suspicious-entity summary plus local context. The curator choices are:

- `accept`: add the suggested span.
- `reject`: mark the suggestion as a verified false positive.
- `skip`: leave it unresolved for a later pass.
- `modify`: correct the span offsets and/or label.

Accepted, rejected, and modified decisions receive a local audit marker of the form `USER:DATE:verified`. Patch application also writes reviewer-neutral public `audit_marks` into the JSONL rows. Later audit queues can suppress verified suggestions with the same span and label, so the same false positive or accepted correction is not repeatedly presented. Skipped decisions are not verified and remain eligible for later review.

Apply accepted and corrected span decisions to a JSONL split:

```bash
make apply-span-patches \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk
```

The defaults point to the active v2.0.0 prerelease empty-training-doc audit. For target-scoped vertical extension, override `SPAN_PATCH_AUDIT_ID`, `SPAN_PATCH_CANDIDATES`, `SPAN_PATCH_SOURCE_JSONL`, and `SPAN_PATCH_TARGET_LABEL`.

Decisions are append-only under:

```text
data/curated/span-patches/<audit-id>/decisions.jsonl
```

Patch application writes a revised JSONL split plus `changes.jsonl`, `changes.tsv`, and `apply_summary.json` under the configured span-patch output directory.

## Build The Review Queue

Run the selected model over the HIPE-derived validation and test folds:

```bash
make curate-legacy-eval \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  CURATION_MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1/best
```

`curate-legacy-eval` includes both the HIPE-derived dev/validation fold and the HIPE-derived test fold. To curate only one fold, use:

```bash
make curate-legacy-validation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  CURATION_MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1/best

make curate-legacy-test \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  CURATION_MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1/best
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

## Review In The Terminal

Review all pending items:

```bash
make review-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  REVIEWER="$USER"
```

For a short test session:

```bash
make review-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  REVIEWER="$USER" \
  ARGS="--limit 20"
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

## Validate Decisions

Validate that the current curation pass is internally consistent:

```bash
make validate-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk
```

`skip` decisions are treated as ignored for this pass and do not block completion. Use the stricter validator only when you intentionally want every disagreement resolved as a concrete correction:

```bash
make validate-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  ARGS="--require-complete"
```

For in-progress snapshots:

```bash
make validate-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  ARGS="--no-require-complete"
```

## Apply Decisions

Apply completed decisions to a new curated JSONL directory:

```bash
make apply-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk
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

## Inspect Changes

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

## Sampled Snippet Curation

Sampled snippets use a lighter workflow than the HIPE-derived dev/test correction pass. Candidate rows should be JSONL and contain at least `id` plus either `text` or `snippet`. The tools also accept rows with `matches` and optional pre-tokenized `tokens`, `token_start_offsets`, and `token_end_offsets`.

The workflow still calls these short review units `snippets`, independent of which Impresso field produced the review text. Internally, sampling moved away from relying on the generic Impresso `snippet` field as the main annotation text. Those search-result previews are useful, but they can miss the highlighted query term or show a lead paragraph instead of the actual Solr hit context.

The default `NEWSAGENCY_SAMPLE_CONTEXT_SOURCE` and `RADIOSTATION_SAMPLE_CONTEXT_SOURCE` is now `full-content`. In that mode the sampler first uses the Solr `matches` fragment to identify the hit, then fetches the full Impresso content item, finds the highlighted match in the article text, and cuts a larger local context around it. `*_SAMPLE_CONTEXT_CHARS` controls the nominal maximum character radius; the default `256` is a practical guess for staying near 128 subtokens in typical review examples. The total context around the match is randomly shortened, but kept at least 100 characters when the article has enough text, and the amount before the match is varied using the sampler seed. This prevents the target mention from always being centered or followed by a fixed-length right context. The original `snippet`, raw `matches`, `match_html`, and cleaned `match_text` are kept as provenance fields.

When API/content fetches are too slow or unavailable, use `NEWSAGENCY_SAMPLE_CONTEXT_SOURCE=match` or `RADIOSTATION_SAMPLE_CONTEXT_SOURCE=match`. That lightweight mode turns each Solr `matches` fragment into its own snippet row and strips the `<em>...</em>` markup, but the resulting snippets can be short or truncated because they are only search-hit fragments.

### News-Agency Snippets

There are two different local data situations:

- Real search snippets come from Impresso search results and follow the same basic shape as `../resources/radiostation_candidates_balanced_v2.jsonl`: `id`, `query`, `candidate_label`, `search_language`, `language`, `matches`, `snippet`, date/media metadata, and optional IIIF fields. This is the default workflow for new curation.
- `data/curated/legacy-import-curated/*.jsonl` contains curated HIPE-derived text, tokens, offsets, and accepted news-agency spans. It can still be converted into bootstrap snippet candidates for testing the scoring/review/export workflow, but those rows are not new evidence.
- The parent sampler file `../newsagencies_by_article.json` contains agency names mapped to Impresso article IDs only. It does not contain snippets or article text, so it cannot directly fill candidate snippet JSONL; it needs an Impresso API fetch step first.

Sample real Impresso search snippets:

```bash
make sample-newsagencies \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG=5 \
  NEWSAGENCY_SAMPLE_MAX_PER_LABEL=5 \
  NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL=3
```

This writes `data/candidates/newsagency_search_snippets.jsonl` by default. Query strings are derived from the trainable labels in `resources/newsagency_seeds.json`, including multilingual aliases. Sampling keeps an append-only issue/entity registry at `data/candidates/sample_entity_pairs.jsonl` by default and skips later results from newspaper issues already sampled for the same canonical label. The default per-round cap is intentionally small: at most five selected samples per entity.

Build a local bootstrap snippet file from the curated HIPE-derived JSONL only when you explicitly want test material from the baseline HIPE-derived folds:

```bash
make build-newsagency-snippets-from-legacy \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk
```

This writes `data/candidates/newsagency_legacy_snippets.jsonl` by default.

Score sampled snippets with the current model:

```bash
make score-newsagency-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  NEWSAGENCY_SNIPPETS=data/candidates/newsagency_search_snippets.jsonl \
  HF_MODEL=impresso-project/mmbert-impresso-mediasources-ner
```

The scorer writes `data/curated/snippets/newsagencies/scored.jsonl` by default. Rows are marked:

- `auto_accepted`: high-confidence prediction matching the candidate agency label. Multi-span snippets are also auto-accepted when every predicted agency span is very confident; those spans are stored explicitly for export.
- `needs_review`: no prediction, low confidence, low margin, label mismatch, uncertain multiple spans, or suspicious boundary.

By default, `AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE` inherits `AUTO_ACCEPT_MIN_CONFIDENCE`, so `AUTO_ACCEPT_MIN_CONFIDENCE=0.95` applies to both single-span and multi-span snippets unless the multi-span threshold is explicitly overridden.

Review uncertain rows:

```bash
make review-newsagency-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  REVIEWER="$USER"
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
make export-newsagency-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk
```

The default outputs are `data/curated/snippets/newsagencies/train.jsonl` and `data/curated/snippets/newsagencies/test.jsonl`. They use the same token-label/entity schema as the HIPE-derived dataset and preserve `source_component` so snippet-derived examples can be mixed deterministically later. The split is deterministic and grouped by source issue/document so snippets from the same source issue do not leak across train and test. Override the holdout size with `SNIPPET_TEST_FRACTION=...`.

`data/curated/` is a local working area. When reviewed snippets are ready to become shared project state, include the resulting full dataset snapshot in `data/releases/<dataset-version>/` before cleaning local state or publishing a new Hugging Face dataset revision.

Useful overrides:

- `AUTO_ACCEPT_MIN_CONFIDENCE=0.95`
- `AUTO_ACCEPT_MIN_MARGIN=0.30`
- `REVIEW_MAX_ITEMS=20`

### Language-Aware Coverage Targets

`make annotation-stats` writes label-level and label-language coverage to `data/curated/annotation_coverage.json`. Targeted sampling and review prioritization use the label-language buckets, so a label with many German examples can still be sampled and reviewed for French, English, Luxembourgish, or Italian gaps.

Default coverage targets are:

- Main languages `de fr en`: 20 accepted examples per label and language.
- Side languages `lb it`: 5 accepted examples per label and language.

Configure these with:

```bash
make annotation-stats \
  CFG=configs/model-v2.0.0.mk \
  ANNOTATION_MAIN_LANGS="de fr en" \
  ANNOTATION_SIDE_LANGS="lb it" \
  ANNOTATION_MAIN_TARGET_PER_LABEL_LANG=20 \
  ANNOTATION_SIDE_TARGET_PER_LABEL_LANG=5
```

Use `ANNOTATION_LANGUAGE_TARGETS` for explicit per-language overrides, for example:

```bash
make annotation-stats CFG=configs/model-v2.0.0.mk ANNOTATION_LANGUAGE_TARGETS="de=30 fr=30 en=20 lb=8 it=8"
```

### Radio-Station Snippets

The default radio-station input is sampled into `data/candidates/radiostation_search_snippets.jsonl` with `make sample-radiostations`. These rows contain `id`, `station`, `query`, `search_language`, `language`, `matches`, `snippet`, date/media metadata, and optional IIIF fields. The sampler uses the same `data/candidates/sample_entity_pairs.jsonl` issue/entity registry as news-agency sampling and defaults to at most five selected samples per entity in one round.

Because the current NER model was trained from HIPE-derived news-agency annotations and the current baseline label map does not contain radio-station labels yet, radio-station scoring combines two sources of span suggestions: deterministic radio-station seed-alias matching and the current NER model's media-agency predictions. This means a search hit sampled for `BBC` can still show a `Reuter` or `Havas` model prediction if the actual snippet contains that agency instead of the searched radio-station mention.

Score sampled radio-station snippets:

```bash
make score-radiostation-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk
```

Review suggested radio-station spans:

```bash
make review-radiostation-spans \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk \
  REVIEWER="$USER"
```

Export accepted radio-station spans:

```bash
make export-radiostation-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v2.0.0.mk
```

This writes `data/curated/snippets/radiostations/train.jsonl` and `data/curated/snippets/radiostations/test.jsonl`. The exporter extends the baseline HIPE-derived label map in memory with labels from `resources/radiostation_seeds.json`, so radio-station rows can be prepared before retraining a model with radio labels. The split is deterministic and grouped by source issue/document.

Radio-station snippets use the same span-review model as news-agency snippets. Rows with no acceptable radio-station span should be rejected or skipped in `review-radiostation-spans`; those decisions remain audit evidence in `data/curated/snippets/radiostations/reviewed.jsonl`, but they do not produce positive token-classification rows.

Before sharing a dataset extension, copy or generate the full release snapshot under `data/releases/<dataset-version>/`. Ignored local review files under `data/curated/` are not preserved by `make clean`.
