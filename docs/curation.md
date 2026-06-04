# Curation Workflow

This document describes how to review and apply corrections for the legacy French/German dev and test folds.

The current workflow is model-assisted: run the trained model on the legacy validation/test data, build gold-vs-prediction disagreement records, review those records in the terminal, validate the decisions, and then write a non-destructive curated JSONL copy.

## Build The Review Queue

Run the selected model over the legacy validation and test folds:

```bash
make curate-legacy-eval \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
  CURATION_MODEL=models/newsagency_radiostation_modernbert_v0.1.0_continue1/best
```

`curate-legacy-eval` includes both the legacy dev/validation fold and the legacy test fold. To curate only one fold, use:

```bash
make curate-legacy-validation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
  CURATION_MODEL=models/newsagency_radiostation_modernbert_v0.1.0_continue1/best

make curate-legacy-test \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
  CURATION_MODEL=models/newsagency_radiostation_modernbert_v0.1.0_continue1/best
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
  CFG=configs/model-v0.1.0.mk \
  REVIEWER="$USER"
```

For a short test session:

```bash
make review-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
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
  CFG=configs/model-v0.1.0.mk
```

`skip` decisions are treated as ignored for this pass and do not block completion. Use the stricter validator only when you intentionally want every disagreement resolved as a concrete correction:

```bash
make validate-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
  ARGS="--require-complete"
```

For in-progress snapshots:

```bash
make validate-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
  ARGS="--no-require-complete"
```

## Apply Decisions

Apply completed decisions to a new curated JSONL directory:

```bash
make apply-curation \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk
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

Sampled snippets use a lighter workflow than the legacy dev/test correction pass. Candidate rows should be JSONL and contain at least `id` plus either `text` or `snippet`. The tools also accept rows with `matches` and optional pre-tokenized `tokens`, `token_start_offsets`, and `token_end_offsets`.

The workflow still calls these short review units `snippets`, independent of which Impresso field produced the review text. Internally, sampling moved away from relying on the generic Impresso `snippet` field as the main annotation text. Those search-result previews are useful, but they can miss the highlighted query term or show a lead paragraph instead of the actual Solr hit context.

The default `NEWSAGENCY_SAMPLE_CONTEXT_SOURCE` and `RADIOSTATION_SAMPLE_CONTEXT_SOURCE` is now `full-content`. In that mode the sampler first uses the Solr `matches` fragment to identify the hit, then fetches the full Impresso content item, finds the highlighted match in the article text, and cuts a larger local context around it. `*_SAMPLE_CONTEXT_CHARS` controls the nominal maximum character radius; the default `256` is a practical guess for staying near 128 subtokens in typical review examples. The total context around the match is randomly shortened, but kept at least 100 characters when the article has enough text, and the amount before the match is varied using the sampler seed. This prevents the target mention from always being centered or followed by a fixed-length right context. The original `snippet`, raw `matches`, `match_html`, and cleaned `match_text` are kept as provenance fields.

When API/content fetches are too slow or unavailable, use `NEWSAGENCY_SAMPLE_CONTEXT_SOURCE=match` or `RADIOSTATION_SAMPLE_CONTEXT_SOURCE=match`. That lightweight mode turns each Solr `matches` fragment into its own snippet row and strips the `<em>...</em>` markup, but the resulting snippets can be short or truncated because they are only search-hit fragments.

### News-Agency Snippets

There are two different local data situations:

- Real search snippets come from Impresso search results and follow the same basic shape as `../resources/radiostation_candidates_balanced_v2.jsonl`: `id`, `query`, `candidate_label`, `search_language`, `language`, `matches`, `snippet`, date/media metadata, and optional IIIF fields. This is the default workflow for new curation.
- `data/curated/legacy-import-curated/*.jsonl` contains text, tokens, offsets, and accepted news-agency spans. It can still be converted into bootstrap snippet candidates for testing the scoring/review/export workflow, but those rows are not new evidence.
- The parent sampler file `../newsagencies_by_article.json` contains agency names mapped to Impresso article IDs only. It does not contain snippets or article text, so it cannot directly fill candidate snippet JSONL; it needs an Impresso API fetch step first.

Sample real Impresso search snippets:

```bash
make sample-newsagencies \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
  NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG=5 \
  NEWSAGENCY_SAMPLE_MAX_PER_LABEL=5 \
  NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL=3
```

This writes `data/candidates/newsagency_search_snippets.jsonl` by default. Query strings are derived from the trainable labels in `resources/newsagency_seeds.json`, including multilingual aliases. Sampling keeps an append-only issue/entity registry at `data/candidates/sample_entity_pairs.jsonl` by default and skips later results from newspaper issues already sampled for the same canonical label. The default per-round cap is intentionally small: at most five selected samples per entity.

Build a local bootstrap snippet file from the curated legacy JSONL only when you explicitly want legacy-derived test material:

```bash
make build-newsagency-snippets-from-legacy \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk
```

This writes `data/candidates/newsagency_legacy_snippets.jsonl` by default.

Score sampled snippets with the current model:

```bash
make score-newsagency-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
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
  CFG=configs/model-v0.1.0.mk \
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
  CFG=configs/model-v0.1.0.mk
```

The output is `data/curated/snippets/newsagencies/train.jsonl`. It uses the same token-label/entity schema as the legacy training dataset and preserves `source_component` so snippet-derived examples can be mixed deterministically later.

Useful overrides:

- `AUTO_ACCEPT_MIN_CONFIDENCE=0.95`
- `AUTO_ACCEPT_MIN_MARGIN=0.30`
- `REVIEW_MAX_ITEMS=20`

### Radio-Station Snippets

The default radio-station input is sampled into `data/candidates/radiostation_search_snippets.jsonl` with `make sample-radiostations`. These rows contain `id`, `station`, `query`, `search_language`, `language`, `matches`, `snippet`, date/media metadata, and optional IIIF fields. The sampler uses the same `data/candidates/sample_entity_pairs.jsonl` issue/entity registry as news-agency sampling and defaults to at most five selected samples per entity in one round.

Because the current NER model was trained from legacy news-agency annotations and the legacy label map does not contain radio-station labels yet, radio-station scoring combines two sources of span suggestions: deterministic radio-station seed-alias matching and the current NER model's media-agency predictions. This means a search hit sampled for `BBC` can still show a `Reuter` or `Havas` model prediction if the actual snippet contains that agency instead of the searched radio-station mention.

Score sampled radio-station snippets:

```bash
make score-radiostation-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk
```

Review suggested radio-station spans:

```bash
make review-radiostation-spans \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
  REVIEWER="$USER"
```

Export accepted radio-station spans:

```bash
make export-radiostation-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk
```

This writes `data/curated/snippets/radiostations/train.jsonl`. The exporter extends the legacy label map in memory with labels from `resources/radiostation_seeds.json`, so radio-station rows can be prepared before retraining a model with radio labels.

For a lighter yes/no-only triage pass, use:

```bash
make review-radiostation-snippets \
  PYTHON=.venv/bin/python \
  CFG=configs/model-v0.1.0.mk \
  REVIEWER="$USER"
```

Choices:

- `yes`: the snippet mentions the target radio station or another canonical radio station.
- `no`: the snippet does not contain a radio-station mention in the annotation-policy sense.
- `skip`: unclear, noisy, or needs more context.

The command writes append-only decisions to `data/curated/snippets/radiostations/decisions.jsonl` and materializes:

- `positive_snippets.jsonl`
- `negative_snippets.jsonl`
- `skipped_snippets.jsonl`
