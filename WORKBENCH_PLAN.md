# Workbench Plan

## Goal

Create a clean workbench-style repository for Impresso news-agency and radio-station training material, model training, evaluation, and Hugging Face publication.

The target shape follows the pattern of `impresso-frakturline-classifier-workbench`:

- The GitHub workbench repo owns source code, curation tools, release configs, tests, source copies of HF cards, and source copies of HF pipeline files.
- Hugging Face dataset repos own published training and benchmark data.
- Hugging Face model repos own published weights, tokenizer/config metadata, model cards, and self-contained inference pipeline code.
- `hub/*` paths are submodules pointing at live HF repos for inspection and pinned revision awareness.
- Training code lives in a dedicated submodule, adapted from `newsagency-classification-main-nikki`, rather than being mixed into the sampling/curation workbench.

This plan intentionally separates three tracks:

1. Searching, sampling, and curation of training material for news agencies and radio stations.
2. Training a modern token-classification model in a new training-code submodule.
3. Deploying models and pipeline code to Hugging Face.

Resolved design decisions:

- Train a single model that predicts both news-agency and radio-station labels.
- Build canonical news-agency labels from `all_newsagencies.txt`.
- Enrich canonical news-agency metadata with Wikipedia page links.
- Publish training data as JSONL, not HIPE TSV.
- Emit inference results as JSONL with offsets.
- Do not support TorchServe initially; use a simple Hugging Face pipeline and adapt the existing `impresso-pipelines` news-agencies pipeline.

## Thesis-Derived Requirements

The underlying master thesis is `report.pdf`, "Where Did the News come from? Detection of News Agency Releases in Historical Newspapers" by Lea Marxen, submitted on 18 August 2023. It documents the original news-agency annotation, model implementation, inference, and corpus analysis. The new workbench should preserve the methodological decisions that still matter while adapting the artifact format and model scope.

### Scope And Definition

The thesis used an explicit-attribution definition:

- A news-agency article is an article that explicitly cites a news agency as a source.
- The annotation target is the agency mention when it signals source attribution.
- Mentions of agencies as article subjects, for example a story about agency staff or an agency acquisition, should not be annotated as source mentions.

For the new workbench, use the broader rule documented in `docs/annotation_guidelines.md`: annotate explicit canonical media-source organization mentions in sampled contexts, including source attributions and article-topic or institutional mentions. Keep canonical trainable labels in `resources/newsagency_seeds.json` and `resources/radiostation_seeds.json`.

### Original Sampling Method

The thesis built a raw corpus by querying Impresso collections for agency names, aliases, abbreviations, and OCR variants. Around 70 agencies were investigated, 27 agency collections were retained, and the raw corpus contained 2,814,382 articles with possible agency mentions.

Important sampling decisions to carry forward:

- Use alias-rich queries, including OCR variants and historical spellings.
- Keep query provenance with every candidate row.
- Treat short/generic acronyms as high-risk false-positive sources.
- Sample uniformly across decades and stratify by entity and newspaper where possible.
- Original target: 100 articles per decade for 1840-1999, plus extra samples when an agency appeared too rarely in a decade.
- Original train/dev/test split: 80/10/10 at document level, stratified by decade and agency.
- Original article filters: years 1840-2000, exclude very short articles below 32 tokens, exclude very long articles above 2,000 tokens, and drop newspapers with too little raw-corpus support.

The thesis notes that German data was underrepresented and that 19th-century candidates produced many false positives. For the new joint model, add explicit balancing targets for language and entity family so radio stations and German examples are not drowned out by French press-agency examples.

### Annotation Rules To Preserve

The original INCEpTION annotation campaign used token-level labels plus document-level `non_usable` for articles too noisy to annotate. It also allowed token-level OCR correction fields for noisy agency mentions.

The current annotator-facing rules are maintained in [docs/annotation_guidelines.md](docs/annotation_guidelines.md). They adapt the thesis rules to sampled search results and short paragraph annotation rather than full long-document annotation.

Rules that should become JSONL curation rules:

- Mark noisy but identifiable mentions and keep the corrected transcript.
- If an article is too noisy to understand, mark it `non_usable` and exclude it from training.
- If OCR makes mention boundaries uncertain, include the characters that should have been part of the mention and store the correction.
- Include periods that are part of abbreviations, for example `D.N.B.` or `ag.`.
- Do not include a sentence-final period after an agency name or acronym, for example annotate `Havas`, not `Havas.`.
- Do not include generic words such as `agence` or `Agentur` unless they are part of the proper name, for example `Agence France Presse`.
- In German compounds, annotate only the agency-name part, for example `Reuter` in `Reutermeldung`.
- Keep article-author attributions out of the entity-label space; the old `pers.ind.articleauthor` tag was a disambiguation aid, not a trainable target for the new model.

### Label Policy From The Thesis

The original annotation tagset contained 27 agency tags plus `ag`, `pers.ind.articleauthor`, and `unk`. During post-processing, some `unk` mentions were corrected to concrete agencies; Kipa and Xinhua received their own tags because they appeared several times in the corpus.

For the new model:

- `unk` must not be a trainable output label.
- `pers.ind.articleauthor` must not be a trainable output label.
- Bare `ag` is not a real news agency in the thesis; it means a generic agency mention such as `ag.`, `agence`, or `Agentur`. If retained, it should be represented as a separate generic source-marker class only after an explicit decision, not as `org.ent.pressagency.ag`.
- Concrete agency labels should be backed by metadata: display name, aliases, country, active dates where known, Wikidata URL, and Wikipedia URL.
- The current `all_newsagencies.txt` list should be audited against the thesis tagset and Appendix B before release metadata is frozen.

### Post-Correction And QA Loop

The thesis post-processing step is directly relevant for the workbench:

- Print and manually inspect all `unk` occurrences.
- Convert `unk` to concrete labels when possible.
- Search for missed annotations by applying the original query terms/aliases as regexes over annotated documents.
- Print each potential missed mention with local context for review.
- Re-annotate documents where missed mentions are found.
- Add derived metadata after curation, including article-level source flags and Wikidata IDs.

In the thesis, this missed-annotation search added 14 German mentions and 71 French mentions. The new curation workflow should include an equivalent `make qa-candidates` or `make audit-missed-mentions` command over JSONL.

### Dataset Facts And Risks

The final thesis dataset contained:

- 1,530 annotated documents.
- 1,058,449 tokens.
- 1,976 annotated agency/article-author mentions.
- 1,133 French documents and 397 German documents.
- 1,236 train documents, 142 dev documents, and 152 test documents.
- 15 German and 65 French articles discarded as too noisy.
- Higher OCR noise in German mentions overall.

Observed risks to address in the new dataset:

- German examples were too sparse, making German training unstable.
- 19th-century examples were sparse and noisy, causing weak inference quality before roughly 1890.
- OCR noise sharply reduced entity-recognition performance.
- The model had high precision but lower recall, often missing mentions rather than confusing agencies.
- Unknown/unseen concrete agencies were poorly recognized as entities even when sentence-level source context was detected.
- Short acronyms and bracketed/dotted forms caused false positives, including cases like `AP`, `ATP`, `FN`, and partial dotted fragments.

Development consequences:

- Preserve precision-oriented evaluation, but track recall explicitly by entity family, language, time period, OCR-noise level, and acronym length.
- Add targeted hard negatives for generic acronyms, author signatures, sports/non-agency acronyms, and dotted fragments.
- Add targeted positive examples for noisy OCR and 19th-century material.
- Keep diagnostics that expose `surface`, offsets, predicted label, confidence, language, year, and source document metadata.

### Model And Evaluation Lessons

The thesis trained BERT-family token classifiers and also experimented with sentence classification. The selected legacy inference used one French model and one German model, with max sequence length 128. Model experiments showed:

- Token-level agency recognition reached roughly F1 0.78 for French and 0.84 for German in the best reported test settings.
- Lookup baselines had strong recall but lower precision, confirming that a pure dictionary approach is not enough for clean corpus analysis.
- In-domain/historical pretraining helped sometimes but was not uniformly superior.
- Multilingual fine-tuning helped multilingual models, especially when one language had less training data.
- Max sequence length 128 or 256 was generally sufficient; 512 added cost and did not clearly improve results.
- OCR noise caused a major performance drop.
- HIPE scoring and in-model scoring differed; the new JSONL scorer should define a single official metric contract and keep conversion checks if old TSV data is imported.

For the new workbench:

- Start with ModernBERT token classification only.
- Keep sentence/article classification out of the first implementation unless there is a later explicit source-detection task.
- Evaluate JSONL span predictions at entity/span level, not only token level.
- Report micro precision/recall/F1 overall and by entity family, language, decade, OCR-noise flag, and label.
- Keep a lookup baseline as a regression benchmark and hard-negative generator.

### Inference Lessons

The original corpus-scale inference processed 24,994,906 French and German articles and detected 4,482,890 agency mentions in 2,406,634 articles. Quality assessment manually checked 160 predicted tokens, five per decade and language.

Findings to carry forward:

- 20th-century predictions were generally reliable.
- Results before roughly 1890 contained many false positives and should be flagged as lower confidence in analysis.
- German quality decreased somewhat in later decades, likely linked to sparse German training support.
- `unk` predictions were unreliable and mixed true agencies with false positives.
- Common false-positive patterns included brackets, following periods, hyphens nearby, dotted fragments, and ambiguous acronyms.

For the new JSONL inference output:

- Include enough provenance to support later manual QA and corpus analysis: article ID, language, date/year, newspaper/media ID, offsets, surface, label, confidence, and metadata links.
- Add optional warning flags for high-risk cases, such as 19th-century predictions, generic acronyms, OCR-noise correction, and low confidence.
- Preserve a diagnostics mode similar to the existing `impresso-pipelines` implementation.

## Proposed Repository Roles

| Role | Proposed location | Purpose |
| --- | --- | --- |
| Workbench GitHub repo | `impresso-mediasources-ner-workbench` | Control plane for sampling, curation, configs, tests, source HF cards, and publish scripts |
| Training code submodule | `training/newsagency-radiostation-modernbert-classifier/` | ModernBERT-only token-classification training/evaluation code adapted from Nikki's repo |
| HF training dataset repo | `impresso-project/impresso-mediaagencies-ner-dataset` | Published curated training data for both entity families |
| HF testset repo | `impresso-project/newsagency-radiostation-testset` | Frozen held-out benchmark |
| HF model repo | `impresso-project/mmbert-impresso-mediasources-ner` | Published model payload and self-contained HF inference pipeline for source-mention NER |
| HF continued-MLM model repo | `impresso-project/mmbert-multilingual-impresso-continued-mlm` | Domain-adapted multilingual mmBERT checkpoint from continued MLM on Impresso text |
| Pipeline reference submodule | `pipeline/impresso-pipelines/` | Existing `impresso-pipelines` package and old news-agency HF pipeline implementation |

The model should support both entity families, but the label namespace must keep them distinct:

- `org.ent.pressagency.<canonical_agency>`
- `org.ent.radiostation.<canonical_station>`

News-agency labels are derived from `all_newsagencies.txt`. Radio-station labels are derived from curated radio-station seed metadata. Do not use generic `unk`, unresolved bare `ag`, or author labels as trainable entity labels.

## Proposed Workbench Layout

```text
impresso-mediasources-ner-workbench/
  AGENTS.md
  README.md
  WORKBENCH_PLAN.md
  Makefile
  pyproject.toml

  configs/
    model-v0.1.0.mk

  lib/
    impresso_auth.py
    search_impresso.py
    sample_newsagencies.py
    sample_radiostations.py
    curate_candidates.py
    export_training_data.py
    publish_dataset.py
    publish_testset.py
    push_model_to_hub.py
    export_pipeline.py

  resources/
    newsagency_seeds.json
    radiostation_seeds.json

  data/
    candidates/
    curated/
    testset/

  hf_dataset/
    README.md

  hf_testset/
    README.md

  hf_model/
    README.md
    pipeline.py
    requirements.txt

  hf_mlm_model/
    README.md

  hub/
    impresso-mediaagencies-ner-dataset/
    newsagency-radiostation-testset/
    mmbert-impresso-mediasources-ner/
    multilingualmodernimpressoBERT/

  training/
    newsagency-radiostation-modernbert-classifier/

  pipeline/
    impresso-pipelines/

  tests/
    fixtures/
    test_sampling_contracts.py
    test_export_training_data.py
```

Large local data, checkpoints, temporary search results, browser state, and generated model artifacts should stay out of source control unless deliberately published as small fixtures.

## Track 1: Searching, Sampling, And Curation

### Objective

Build a repeatable pipeline to find, sample, review, and export training material for one joint classifier with two entity families:

- Real news agencies.
- Radio-station mentions.

The current repository already contains useful starting points:

- `sampling_articles.py`: agency-based Impresso sampling.
- `getting_client.py`: browser/token helper for Impresso API authentication.
- `sample_radiostation_candidates_balanced.py`: balanced radio-station candidate sampling.
- `build_radiostation_candidates_balanced_v2.py`: more structured radio-station candidate collection.
- `resources/radiostation_*`: seed and candidate examples.
- `all_newsagencies.txt` and `newsagencies_by_article.json`: current agency seed/results material.

### Workbench Tasks

Status: todo unless marked otherwise.

- [ ] Normalize all news-agency seeds from `all_newsagencies.txt` into `resources/newsagency_seeds.json`.
- [ ] Enrich each canonical news-agency entry with a stable `wikipedia_url`.
- [ ] Normalize radio-station seeds into `resources/radiostation_seeds.json`.
- [ ] Split Impresso authentication into `lib/impresso_auth.py`, with no credentials in source control.
- [ ] Create one reusable search client wrapper for retries, pauses, token refresh, and logging.
- [ ] Convert agency sampling into a CLI: `python -m lib.sample_newsagencies`.
- [ ] Convert radio-station sampling into a CLI: `python -m lib.sample_radiostations`.
- [ ] Write JSONL candidate outputs with stable schema and provenance fields.
- [ ] Add dry-run and `--max-docs` options for all sampling commands.
- [ ] Add deterministic sampling controls, including random seed and query/date/language limits.
- [ ] Add curation commands that operate on local candidate JSONL files, not directly on HF evaluation rows.
- [ ] Define curation status values such as `accepted`, `rejected`, `needs_context`, `duplicate`, and `wrong_entity_type`.
- [ ] Export accepted news-agency and radio-station material into training JSONL.
- [ ] Keep rejected and ambiguous radio-station/news-agency material as curation evidence, not trainable labels.
- [ ] Add small fixtures and tests for candidate schema validation and export behavior.

### Applying HIPE-Derived Evaluation Curation

Implemented for the HIPE-derived French/German dev and test folds:

- Generate model-vs-gold disagreements with `make curate-legacy-eval`.
- Store reviewer decisions append-only in `data/curated/legacy-eval-curation/review/decisions.jsonl`.
- Validate completed decisions with `make validate-curation`.
- Apply completed decisions with `make apply-curation`, writing revised JSONL to `data/curated/legacy-import-curated/`.

The command and path names keep `legacy-*` for compatibility. Conceptually, this is still active HIPE-derived baseline data, not discarded data.

The apply step is intentionally non-destructive. It reads `data/curated/legacy-import/` and writes a new output directory containing revised `train.jsonl`, `validation.jsonl`, `test.jsonl`, `label_map.json`, `curation_changes.jsonl`, and `curation_summary.json`.

Decision semantics:

- `gold`: keep this row's gold span unless a correction note is supplied.
- `prediction`: add or replace the overlapping gold span with the prediction span; if a correction note is supplied, use the corrected span instead.
- `neither`: remove displayed overlapping spans; if a correction note is supplied, add that corrected span.
- `both`: keep/add both displayed spans only when they can be represented as non-overlapping BIO spans.
- `skip`: records an audit row but should not be used for final complete curation.

Correction notes use a copyable syntax emitted by the terminal reviewer:

```text
13:15 "Agence Wolff" label=org.ent.pressagency.wolff
```

After applying decisions, the script rebuilds `entities`, `token_labels`, and `token_label_ids`, regenerates `label_map.json`, validates the public JSONL schema, and writes an audit row for every applied decision.

### Canonical Label Metadata

News-agency labels come from `all_newsagencies.txt`. The normalization step should create structured metadata rather than relying on bare strings:

```json
{
  "canonical_id": "reuters",
  "label": "org.ent.pressagency.reuters",
  "display_name": "Reuters",
  "aliases": ["Reuters"],
  "wikipedia_url": "https://en.wikipedia.org/wiki/Reuters",
  "wikidata_url": "https://www.wikidata.org/wiki/Q130879"
}
```

Radio-station metadata should use the same shape with `org.ent.radiostation.*` labels. Wikipedia links are required for news agencies where a page exists; missing or uncertain links should be explicit `null` values with a curation note, not guessed URLs.

Initial news-agency canonical IDs from `all_newsagencies.txt`:

```text
reuters
stefani
extel
havas
xinhua
domei
belga
ctk
ansa
dnb
wolff
afp
up-upi
ats-sda
dpa
kipa
ag
ap
apa
ddp-dapd
tass
europapress
spk-smp
```

These IDs should be normalized into display names, aliases, canonical labels, Wikidata URLs where available, and Wikipedia URLs. Entries that are ambiguous or historically overloaded, especially short labels such as `ag`, must be disambiguated with a Wikipedia-backed metadata record before they become trainable labels.

### Candidate Schema

Use one JSON object per line. Keep enough provenance for later audit and reproducibility:

```json
{
  "id": "content-item-id",
  "entity_type": "pressagency",
  "candidate_label": "org.ent.pressagency.reuters",
  "query": "Reuters",
  "search_language": "fr",
  "language": "fr",
  "date": "1946-09-27T00:00:00+00:00",
  "mediaId": "example-paper",
  "matches": ["..."],
  "snippet": "...",
  "source": {
    "api": "impresso",
    "searched_at": "YYYY-MM-DD",
    "date_range": ["1925-01-01", "1960-12-31"]
  },
  "curation": {
    "status": "todo",
    "label": null,
    "notes": null
  }
}
```

Accepted curation should resolve to a canonical label in either the `pressagency` or `radiostation` namespace.

### Sampled Snippets To Additional Training Data

Goal: turn sampled short text snippets into additional supervised training data with minimal human work while avoiding self-training drift.

The workflow should treat news-agency snippets and radio-station snippets differently.

Text source policy:

- Continue to call the short review/training units `snippets`. The name describes the curation unit, not the exact Impresso source field.
- Do not rely on the generic Impresso search-result `snippet` as the primary annotation text. It is a search preview and may not contain the highlighted query term.
- Use Solr `matches` fragments to identify the hit that motivated the snippet.
- Prefer full-content context windows for normal sampling: fetch the full Impresso content item, locate the Solr match inside the article text, and cut a local context window around the match.
- Keep the original `snippet`, raw `matches`, `match_html`, and cleaned `match_text` fields as provenance, but score/review the normalized `text` field.
- Use a configurable context radius for full-content mode. The current default is 256 characters, chosen as a practical guess for review windows near 128 subtokens. Randomize the total context length and the amount before the match, with a seeded RNG, so target mentions do not always appear in the same relative position and are not always followed by fixed-length right context. Keep at least 100 characters of context when enough article text is available.
- Keep a lightweight `match` mode for cases where full-content fetches are too slow or unavailable. In that mode each highlighted match becomes its own snippet candidate row, with `<em>...</em>` markup stripped before scoring and review, but snippets may be short or truncated.

#### News-Agency Snippets: Model-Assisted Active Learning

News agencies already have a model trained from HIPE-derived agency annotations and canonical labels. Use the current model as a proposal generator, not as an unquestioned annotator.

Pipeline:

1. Sample snippets by canonical news-agency query, alias, language, newspaper, and date bucket.
2. Run the current `mmbert-impresso-mediasources-ner` model on each snippet.
3. Convert model output into candidate spans with confidence and margin metadata.
4. Auto-accept only high-confidence, policy-compatible predictions when the predicted label matches the sampled canonical agency or a known alias-compatible canonical label.
5. Send uncertain or suspicious cases to manual span review.
6. Export only accepted spans into additional JSONL training rows.
7. Keep rejected, skipped, and uncertain cases as audit evidence and as future active-learning candidates.

Manual review should be required when:

- no agency span is predicted in a snippet sampled for a concrete agency
- the predicted label differs from the query agency
- the confidence is below a configurable threshold
- competing labels have a small confidence margin
- the predicted span boundary includes only a generic token such as `Agence`, `Agentur`, or punctuation-adjacent fragments
- multiple possible agencies are present
- OCR or abbreviation noise makes the canonical identity unclear

Suggested candidate fields:

```json
{
  "id": "snippet-id",
  "entity_family": "pressagency",
  "candidate_label": "org.ent.pressagency.reuters",
  "query": "Reuters",
  "text": "...",
  "tokens": ["..."],
  "model": {
    "repo_id": "impresso-project/mmbert-impresso-mediasources-ner",
    "revision": "<sha>",
    "predicted_spans": [
      {
        "token_start": 12,
        "token_stop": 13,
        "label": "org.ent.pressagency.reuters",
        "surface": "Reuters",
        "confidence": 0.97,
        "margin": 0.42
      }
    ]
  },
  "curation": {
    "status": "auto_accepted|needs_review|accepted|rejected|skipped",
    "reviewer": null,
    "reviewed_at": null,
    "notes": null
  }
}
```

Implementation tasks:

- [ ] Add `make score-newsagency-snippets` to run the current model over sampled news-agency snippets.
- [ ] Add configurable thresholds for `AUTO_ACCEPT_MIN_CONFIDENCE`, `AUTO_ACCEPT_MIN_MARGIN`, and `REVIEW_MAX_ITEMS`.
- [ ] Add a review queue for low-confidence or mismatched news-agency snippets.
- [ ] Add an export command that writes accepted snippet annotations into the same public JSONL schema as the HIPE-derived baseline dataset.
- [ ] Track the source model revision in every auto-accepted record.
- [ ] Keep auto-accepted and manually accepted rows distinguishable in audit metadata.

#### Radio-Station Snippets: Pre-Annotated Span Review

Radio stations do not yet have reliable model-only span annotations in the current training data. Use deterministic seed-alias matching as the primary proposal generator, optionally add ModernBERT media-source predictions, and send the resulting candidate spans to the same span-review workflow used for news-agency snippets.

The reviewer should see proposed spans with canonical `org.ent.radiostation.*` labels and enough provenance to decide whether each span is valid. Search windows without a valid radio-station span should be rejected or skipped in the reviewed JSONL stream; they remain useful audit and negative evidence, but they do not become positive token-classification rows.

Review cases should include:

- no alias span matched in a snippet sampled for a concrete station
- multiple possible stations are present
- a press-agency span is also proposed by the current NER model
- the alias boundary is suspicious because of OCR, punctuation, or abbreviation noise
- the canonical label cannot be resolved from `resources/radiostation_seeds.json`

For minimal first implementation, the workflow is:

```text
make score-radiostation-snippets
make review-radiostation-spans
make export-radiostation-snippets
```

Implementation tasks:

- [ ] Score sampled radio-station snippets with deterministic alias spans and optional ModernBERT token-classification spans.
- [ ] Reuse the span-review command with radio-station label metadata.
- [ ] Store decisions append-only in `data/curated/snippets/radiostations/decisions.jsonl`.
- [ ] Write reviewed rows to `data/curated/snippets/radiostations/reviewed.jsonl`.
- [ ] Require canonical `org.ent.radiostation.*` labels before any radio-station row enters training data.

#### Training Integration

Additional snippet-derived rows should not immediately replace the HIPE-derived baseline dataset. Build them as a separate dataset component first:

```text
data/curated/snippets/
  newsagencies/train.jsonl
  newsagencies/test.jsonl
  radiostations/reviewed.jsonl
  radiostations/train.jsonl
  radiostations/test.jsonl
  audit/
```

Then combine with the HIPE-derived JSONL through a deterministic merge command:

```text
make build-training-mixture
```

The mixture command should:

- preserve `source_component`, for example `legacy_hipe`, `newsagency_snippet_auto`, `newsagency_snippet_manual`, `radiostation_snippet_manual`
- keep validation/test frozen unless explicitly creating a new development set
- keep snippet-derived train/test splits separate and deterministic, grouped by source issue/document to avoid leakage
- cap auto-accepted news-agency snippets per label/date/language so frequent agencies do not dominate
- oversample manually reviewed radio-station positives when training, rather than duplicating rows in the dataset file
- write a mixture summary with row counts by source component, language, label, decade, and curation status

Quality rule: auto-accepted news-agency snippets are acceptable as training expansion only after spot-checking a random sample per label/language/date bucket. Radio-station snippets require accepted spans from the span-review workflow before they become positive token-classification rows.

### Curation Policy

- Only accepted real news-agency and radio-station spans become labels for the classifier.
- Unknown, ambiguous, generic, or wrong-type mentions must not become model labels.
- `unk` labels from the historical training repo must be converted to `O` or excluded according to the final data policy.
- Radio-station examples are first-class training material, but they must use `org.ent.radiostation.*` labels and must not expand the news-agency label vocabulary.
- Curation tools must preserve the original candidate row and append decisions; avoid destructive rewrites.

## HIPE-Derived TSV To JSONL Format

The standalone field reference is [docs/jsonl_schema.md](docs/jsonl_schema.md). The concrete migration workflow is [docs/hipe_to_jsonl_conversion_plan.md](docs/hipe_to_jsonl_conversion_plan.md). This plan section captures the implementation decisions and migration tasks.

### Objective

Convert the existing HIPE/CLEF-style TSV annotation files from the historical training repo into the new multilingual JSONL format without losing language, source metadata, layout evidence, OCR correction evidence, or entity-linking information.

The historical files use document-level comments plus 13 token columns:

```text
TOKEN
NE-COARSE-LIT
NE-COARSE-METO
NE-FINE-LIT
NE-FINE-METO
NE-FINE-COMP
NE-NESTED
NEL-LIT
NEL-METO
RENDER
SEG
OCR-INFO
MISC
```

Observed document metadata includes:

- `language`
- `newspaper`
- `date`
- `document_id`
- `news-agency-as-source`
- repeated `segment_iiif_link` comments
- `global.columns`

The JSONL importer must preserve these fields and must not assume that file path language is sufficient. In multilingual files, the authoritative language is the per-document `# language = ...` comment.

For the first HIPE-derived import, use only the six monolingual `annotated_data/de/*.tsv` and `annotated_data/fr/*.tsv` files. Ignore `annotated_data/multilingual/*.tsv`: those files are derived convenience concatenations and do not include the full `fr/dev` and `de/test` source material.

### Hugging Face Dataset Layout

The published annotated files should look like a normal Hugging Face dataset:

```text
data/
  train.jsonl
  validation.jsonl
  test.jsonl
  label_map.json
  dataset_card_data.json
```

Use one JSON object per document per line. Prefer split-specific files over a required `split` column because this maps directly to `load_dataset("json", data_files={...})`, the Hub dataset viewer, and common training scripts. A `split` field may be retained for audit, but it should duplicate the file membership rather than define it.

The primary JSONL row should be flat at the top level, with repeated fields represented as arrays. Deep archival details belong in optional sidecar files or audit columns, not in the minimum training row. Character offsets refer to the normalized `text` field, not to the original TSV line byte offsets.

Recommended repository files:

- `data/train.jsonl`, `data/validation.jsonl`, `data/test.jsonl`: public annotated records.
- `data/audit/*.jsonl`: optional richer conversion records with original TSV columns and excluded entities.
- `label_map.json`: deterministic BIO label map used by training and inference.
- `README.md`: dataset card with features, label policy, citation, license, and known limitations.

### Primary Annotated Row Schema

```json
{
  "schema_version": "mediasources-jsonl-v0.1",
  "id": "DTT-1945-08-09-a-i0008",
  "split": "validation",
  "source_format": "hipe-tsv",
  "source_file": "data/annotated_data/de/newsagency-data-dev-de.tsv",
  "language": "de",
  "newspaper": "DTT",
  "date": "1945-08-09",
  "year": 1945,
  "document_id": "DTT-1945-08-09-a-i0008",
  "news_agency_as_source": ["Q1525848", "Q493845"],
  "text": "Der rekonstruierte Modelltext ...",
  "tokens": ["United", "Preß"],
  "token_start_offsets": [0, 7],
  "token_end_offsets": [6, 12],
  "token_labels": [
    "B-org.ent.pressagency.up-upi",
    "I-org.ent.pressagency.up-upi"
  ],
  "token_label_ids": [17, 18],
  "token_nel": ["Q493845", "Q493845"],
  "token_ocr": ["LED0.00", "LED0.00"],
  "token_render": ["_", "_"],
  "token_segment_ids": [0, 0],
  "segments": [
    {
      "index": 0,
      "iiif_link": "https://...",
      "token_start": 0,
      "token_stop": 12,
      "text_start": 0,
      "text_stop": 74
    }
  ],
  "sentences": [
    {
      "index": 0,
      "token_start": 0,
      "token_stop": 12,
      "text_start": 0,
      "text_stop": 74
    }
  ],
  "entities": [
    {
      "entity_id": "DTT-1945-08-09-a-i0008#ent-0",
      "token_start": 0,
      "token_stop": 2,
      "start": 0,
      "stop": 12,
      "surface": "United Preß",
      "normalized_surface": "United Press",
      "label_original": "org.ent.pressagency.UP-UPI",
      "label": "org.ent.pressagency.up-upi",
      "entity_family": "pressagency",
      "nel": "Q493845",
      "wikidata_url": "https://www.wikidata.org/wiki/Q493845",
      "has_ocr_correction": false,
      "max_ocr_levenshtein": 0.0,
      "status": "accepted"
    }
  ],
  "quality_flags": [
    "has_ocr_corrections"
  ]
}
```

This layout supports both common token-classification training and span-level evaluation:

- `tokens` and `token_labels` are the familiar token-classification columns.
- `token_label_ids` makes training deterministic once `label_map.json` is fixed.
- `text`, character offsets, and `entities` support span-level scoring and JSONL inference.
- Top-level columns such as `language`, `newspaper`, `date`, and `year` support filtering and dataset viewer use.
- `segments` and `sentences` keep IIIF and sentence context without making every token a nested object.

The full archival conversion record may be written separately for audit. It can include original token-column dictionaries, `layout_text`, `excluded_entities`, `metadata.original_comments`, and converter provenance. The public training files should not require consumers to parse that archival shape.

### Suggested Hugging Face Features

The dataset card should document features equivalent to:

```python
{
    "schema_version": "string",
    "id": "string",
    "split": "string",
    "source_format": "string",
    "source_file": "string",
    "language": "string",
    "newspaper": "string",
    "date": "string",
    "year": "int32",
    "document_id": "string",
    "news_agency_as_source": ["string"],
    "text": "string",
    "tokens": ["string"],
    "token_start_offsets": ["int32"],
    "token_end_offsets": ["int32"],
    "token_labels": ["string"],
    "token_label_ids": ["int32"],
    "token_nel": ["string"],
    "token_ocr": ["string"],
    "token_render": ["string"],
    "token_segment_ids": ["int32"],
    "segments": [
        {
            "index": "int32",
            "iiif_link": "string",
            "token_start": "int32",
            "token_stop": "int32",
            "text_start": "int32",
            "text_stop": "int32",
        }
    ],
    "sentences": [
        {
            "index": "int32",
            "token_start": "int32",
            "token_stop": "int32",
            "text_start": "int32",
            "text_stop": "int32",
        }
    ],
    "entities": [
        {
            "entity_id": "string",
            "token_start": "int32",
            "token_stop": "int32",
            "start": "int32",
            "stop": "int32",
            "surface": "string",
            "normalized_surface": "string",
            "label_original": "string",
            "label": "string",
            "entity_family": "string",
            "nel": "string",
            "wikidata_url": "string",
            "has_ocr_correction": "bool",
            "max_ocr_levenshtein": "float32",
            "status": "string",
        }
    ],
    "quality_flags": ["string"],
}
```

Avoid relying on arbitrary nested `metadata` dictionaries in the main files. They are convenient locally, but flatter, named columns are easier to inspect in the Hub viewer, easier to filter in `datasets`, and safer for Arrow schema inference.

### Text And Offset Reconstruction

The converter must build deterministic text from the token stream and `RENDER` values:

- `text` is the normalized model text used for training, evaluation, and inference offsets.
- `layout_text` is optional and may preserve line breaks for audit, but official offsets do not point into it.
- Default token rendering inserts one space after a token.
- `NoSpaceAfter` suppresses the following space; this is required for abbreviations such as `D . N . B .` and dotted acronyms.
- `EndOfLine` should be retained in token metadata and may add a newline in `layout_text`; it should become a single whitespace boundary in normalized `text`.
- `SEG = EndOfSentence` closes a sentence span.
- Every token must receive `start` and `stop` offsets into `text`.
- Every entity, segment, and sentence span must include both token offsets and character offsets.

### Entity Conversion

Use `NE-FINE-LIT` as the source of trainable entity labels. Merge contiguous `B-`/`I-` spans with the same base label into one entity span.

Conversion rules:

- Preserve the original TSV label in `label_original`.
- Normalize accepted labels into lowercase canonical IDs, for example `org.ent.pressagency.UP-UPI` becomes `org.ent.pressagency.up-upi`.
- Map accepted historical agency labels through `resources/newsagency_seeds.json`; do not invent canonical IDs during import.
- Map accepted radio-station labels through `resources/radiostation_seeds.json` once radio-station annotation exists.
- Keep `NEL-LIT` QIDs as `nel` and derive `wikidata_url` when present.
- Parse `OCR-INFO` into both `raw` and structured fields. Examples include `LED0.00` and `Transcript:Reuter|LED0.17`.
- Compute entity OCR summary fields from covered tokens: `has_correction`, `max_levenshtein`, and `transcript`.
- Put `unk`, `pers.ind.articleauthor`, unresolved bare `ag`, malformed BIO spans, and wrong-family labels into `excluded_entities` unless a curator resolves them to an accepted canonical label.
- Add `quality_flags` for documents with excluded legacy labels, OCR corrections, malformed BIO spans, missing metadata, or offset reconstruction anomalies.

### Split And Metadata Rules

- Derive `split` from the source filename when possible: `train`, `validation`, or `test`. Map legacy `dev` to Hugging Face-style `validation`.
- Preserve `source_file` relative to the workbench or imported-data root.
- Preserve the original `document_id` even when it equals top-level `id`.
- Normalize `news-agency-as-source` into top-level `news_agency_as_source` as a list of QIDs or raw identifiers.
- Preserve every `segment_iiif_link` as a segment-level field and copy the active segment link onto each token that belongs to it.
- Keep unknown comment fields in the audit JSONL under `metadata.original_comments` rather than dropping them.

### Validation Requirements

The converter should emit a machine-readable validation report with:

- document, token, sentence, segment, entity, and excluded-entity counts
- counts by language, split, label, entity family, newspaper, and decade
- missing or malformed required metadata
- unknown labels not found in seed metadata
- forbidden labels encountered
- offset mismatch count
- malformed BIO count
- OCR correction counts and max `LED` buckets
- segment records without IIIF links

The workbench should include a tiny HIPE fixture and expected JSONL fixture so import behavior is testable without the full historical dataset.

### Migration Tasks

- [ ] Follow [docs/hipe_to_jsonl_conversion_plan.md](docs/hipe_to_jsonl_conversion_plan.md) for the detailed implementation workflow.
- [ ] Add `lib.import_legacy_hipe_tsv` to convert one or more HIPE TSV files into JSONL.
- [ ] Add `make import-legacy-hipe ARGS="--input ... --output data/curated/legacy-import"` as the public workbench entry point.
- [ ] Export split-specific HF files: `train.jsonl`, `validation.jsonl`, and `test.jsonl`.
- [ ] Export optional audit JSONL separately from the primary training files.
- [ ] Generate `label_map.json` and fill `token_label_ids` deterministically from `token_labels`.
- [ ] Add `--forbidden-label-policy exclude|review|error`; default to `exclude`.
- [ ] Add deterministic label normalization backed by `resources/newsagency_seeds.json` and `resources/radiostation_seeds.json`.
- [ ] Add offset reconstruction tests for `NoSpaceAfter`, dotted abbreviations, `EndOfLine`, and `EndOfSentence`.
- [ ] Add tests for OCR parsing examples: `LED0.00`, `Transcript:Reuter|LED0.17`, and `Transcript:B. N.|LED1.00`.
- [ ] Add a validation report command for imported JSONL.
- [ ] Review all `excluded_entities` before publishing the first converted dataset.

## Track 2: Training Submodule

### Objective

Create a new training-code repository and add it as a submodule under `training/newsagency-radiostation-modernbert-classifier/`.

Before supervised token classification, support continued masked-language-model pretraining on multilingual Impresso text. This produces a domain-adapted base checkpoint, planned as `impresso-project/mmbert-multilingual-impresso-continued-mlm`, which is then used as the default base model for media-source NER.

The new training repo should take the useful modernBERT token-classification ideas from:

```text
/Users/siclemat/pj/2025/impresso/newsagency-classification-main-nikki
```

Its `AGENTS.md` says the migration target should be much narrower than the historical repo:

- Keep modernBERT-only token classification.
- Drop sequence/article-level classification.
- Drop generic legacy model-family sweeps.
- Keep only real news-agency labels plus curated radio-station labels.
- Remove `B-org.ent.pressagency.unk` and `I-org.ent.pressagency.unk` from the canonical label vocabulary.
- Generate `label_map.json` deterministically.
- Load labels from artifacts for inference instead of hard-coded maps.

### Continued MLM Domain Adaptation

The old development workflow included continued masked-language-model pretraining before supervised agency classification. The new workbench should preserve that idea, but make it explicit and reproducible:

- Start from the multilingual ModernBERT-family checkpoint `jhu-clsp/mmBERT-base`.
- Build a balanced multilingual Impresso MLM corpus from compiled Impresso JSONL files.
- Use the same basic objective as the old script: MLM with probability `0.15`.
- Keep the first larger run balanced by capping each language at 300,000 texts, using all available examples for smaller languages such as Luxembourgish. Hold out only 1 percent for MLM validation. The older 50,000-document experiment remains reproducible by overriding `MLM_MAX_PER_LANGUAGE=0 MLM_TARGET_TOTAL=50000`.
- Use a tested Apple MPS local default: `MLM_MAX_LEN=256`, fixed max-length padding, `MLM_BATCH=1`, `MLM_GRADIENT_ACCUMULATION_STEPS=8`, and gradient checkpointing, for an effective per-device batch of 8.
- Use conservative optimization defaults for continued pretraining: one epoch, learning rate `2e-5`, weight decay `0.01`, and explicit warmup steps equivalent to roughly 6 percent of the expected optimizer steps.
- Keep the full sampled MLM JSONL on disk, but allow capped training views. The local default trains on 100,000 sampled rows and validates on 2,000 rows.
- Run MLM validation three times across the epoch plus one final evaluation, using only a 1 percent validation split.
- Disable intermediate checkpoint saving by default and save only the final adapted model unless `MLM_SAVE_STRATEGY=steps` or `epoch` is explicitly requested.
- Tokenize MLM data into a reusable Arrow cache under `mlm.d/`. Use fixed max-length padding by default for Apple MPS stability; dynamic padding can be re-enabled with `MLM_PAD_TO_MAX_LENGTH=false`.
- Save the local adapted checkpoint under `models.d/multilingualmodernimpressoBERT_v0.1.0/final`.
- Publish the adapted checkpoint to the separate HF model repo `impresso-project/mmbert-multilingual-impresso-continued-mlm`.
- Use the published adapted checkpoint as the default `BASE_MODEL` for the supervised news-agency and radio-station token classifier: `hf://impresso-project/mmbert-multilingual-impresso-continued-mlm`. Allow users to override this with a local path or a plain Hugging Face model id.
- Use memory-conservative local supervised training defaults on Apple MPS: microbatch 1, gradient accumulation, gradient checkpointing, Adafactor instead of AdamW, and frozen encoder/head-only training by default. Full encoder fine-tuning remains available with `FREEZE_BASE_MODEL=false` on hardware with enough memory.
- At supervised-training startup, emit a machine-readable report with model source, device, optimizer, parameter counts, frozen/unfrozen layer setup, batch/window settings, train/validation row summaries, and early-stopping configuration.
- Evaluate validation after each supervised epoch, use early stopping on `entity_f1`, and save the best validation checkpoint separately.
- During validation and final test evaluation, report the NER-specific facts needed to judge tagging behavior: exact entity precision/recall/F1, gold/predicted/correct entity counts, non-`O` token precision/recall/F1, token accuracy, and the top entity labels by gold and predicted frequency.

The immediate implementation is based on the older root-level scripts:

- `build_balanced_multilingual_50k_from_compiled_lbfix.py`
- `mlm_multilingual_train_50k.py`

The new workbench equivalents are:

- `make build-mlm-data`: writes `mlm.d/multilingual_50k_lbfix/train.json`, `validation.json`, and `dataset_report.json`.
- `make download-mlm-sources`: downloads the compiled source files from configured Switch/S3 URLs into `mlm.d/source/`.
- `make pretrain-mlm`: continues MLM training and writes the adapted checkpoint plus metrics.
- `hf_mlm_model/README.md`: source model card for the future HF repository.

The corpus input is expected at `mlm.d/source/{fr,de,en,lb}.compiled.jsonl.bz2` by default. The source directory is controlled by `MLM_DATASET_DIR`; the download URLs are controlled by `MLM_SOURCE_URL_DE`, `MLM_SOURCE_URL_FR`, `MLM_SOURCE_URL_EN`, `MLM_SOURCE_URL_LB`, and `MLM_SOURCE_URLS` in `configs/model-v0.1.0.mk`.

Open implementation tasks:

- [ ] Run `make download-mlm-sources PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk`, or override the `MLM_SOURCE_URL_*` variables if the source location changes.
- [ ] Run `make build-mlm-data PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk`; override `MLM_MAX_PER_LANGUAGE` for smaller or larger MLM samples.
- [ ] Inspect `mlm.d/multilingual_50k_lbfix/dataset_report.json` for language balance, skipped-record counts, and OCR-quality effects.
- [ ] Run a short `make pretrain-mlm` smoke test with tiny `ARGS` before full training if compute is constrained.
- [ ] Run full continued MLM pretraining and publish the resulting checkpoint to `impresso-project/mmbert-multilingual-impresso-continued-mlm`.
- [ ] Train the supervised classifier from `models.d/multilingualmodernimpressoBERT_v0.1.0/final`.
- [ ] Compare supervised dev/test metrics against training directly from `jhu-clsp/mmBERT-base`.

### Training Repo Shape

```text
newsagency-radiostation-modernbert-classifier/
  AGENTS.md
  README.md
  pyproject.toml
  Makefile

  src/newsagency_radiostation_modernbert/
    data.py
    labels.py
    model.py
    train.py
    evaluate.py
    predict.py
    postprocess.py

  scripts/
    pretrain_mlm_multilingual.sh
    train_modernbert_multilingual.sh
    eval_jsonl.sh

  tests/
    fixtures/
      tiny_training.jsonl
      tiny_label_map.json
    test_labels.py
    test_dataset.py
    test_jsonl_prediction_writer.py

  hf_pipeline/
    pipeline.py
    requirements.txt
```

### Training Data Contract

The final published and trainable data format is the document-level JSONL schema defined in `HIPE-Derived TSV To JSONL Format`. The training submodule may load a reduced projection of those rows, but it must preserve enough source metadata to write auditable prediction JSONL.

Minimum training projection per document:

```json
{
  "id": "content-item-id",
  "text": "Selon Reuters ...",
  "language": "fr",
  "source": {
    "mediaId": "example-paper",
    "date": "1946-09-27T00:00:00+00:00",
    "impresso_id": "content-item-id"
  },
  "entities": [
    {
      "start": 6,
      "stop": 13,
      "surface": "Reuters",
      "label": "org.ent.pressagency.reuters"
    }
  ]
}
```

The training loader should accept the full workbench JSONL and internally use the minimum projection above. For migration from Nikki's HIPE/TSV code, import old `NE-FINE-LIT` labels into JSONL spans before training instead of training directly on TSV.

The exported label vocabulary must contain:

- `O`
- `B-org.ent.pressagency.<canonical_real_agency>`
- `I-org.ent.pressagency.<canonical_real_agency>`
- `B-org.ent.radiostation.<canonical_station>`
- `I-org.ent.radiostation.<canonical_station>`

It must not contain:

- `B-org.ent.pressagency.unk`
- `I-org.ent.pressagency.unk`
- generic organization labels that are not real news agencies
- unresolved bare `ag`
- `pers.ind.articleauthor`

### Training Tasks

- [ ] Create the new training-code repository.
- [ ] Add it as a Git submodule at `training/newsagency-radiostation-modernbert-classifier/`.
- [ ] Migrate and simplify the dataset reader from Nikki's repo.
- [ ] Replace TSV as the primary training input with JSONL text/span rows.
- [ ] Migrate modernBERT compatibility logic that omits unsupported `token_type_ids`.
- [ ] Replace the custom sequence-and-token classifier with token classification only.
- [ ] Implement deterministic label-map generation from curated training material.
- [ ] Add a label-policy test that fails if `*.unk`, unresolved bare `ag`, or `pers.ind.articleauthor` labels appear.
- [ ] Add small JSONL fixtures for parsing, token alignment, and prediction writing.
- [ ] Keep TSV conversion tests only as migration coverage if TSV import remains supported.
- [ ] Add one smoke test for a tiny forward pass or mocked model path.
- [ ] Implement evaluation with seqeval over JSONL token/span records.
- [ ] Ensure prediction JSONL preserves source identifiers, text offsets, surfaces, and metadata.
- [ ] Package training code as a real Python package with absolute imports.

### Workbench Integration

The workbench should not duplicate training internals. It should call the training submodule through stable public commands:

```bash
make train CFG=configs/model-v0.1.0.mk
make test CFG=configs/model-v0.1.0.mk
make test-official CFG=configs/model-v0.1.0.mk
```

Release config files in the workbench should pin:

```makefile
MODEL := models.d/newsagency_radiostation_modernbert_v0.1.0
DATASET := impresso-project/impresso-mediaagencies-ner-dataset
DATASET_REVISION := <training-dataset-commit-sha>
TESTSET := impresso-project/newsagency-radiostation-testset
TESTSET_REVISION := <testset-commit-sha>
BASE_MODEL := jhu-clsp/mmBERT-base
EPOCHS := 3
BATCH := 16
MAX_SEQUENCE_LEN := 512
SEED := 42
```

The produced model config must record exact dataset revisions, label map, base model, hyperparameters, and official evaluation metrics.

## Track 3: Hugging Face Deployment

### Objective

Publish data, models, and inference code to Hugging Face so downstream users do not need the workbench checkout.

### HF Repositories

| Artifact | Proposed repo | Contents |
| --- | --- | --- |
| Training data | `impresso-project/impresso-mediaagencies-ner-dataset` | Curated JSONL training examples and metadata for both entity families |
| Official test set | `impresso-project/newsagency-radiostation-testset` | Frozen JSONL held-out benchmark with versioned membership |
| Model payload | `impresso-project/mmbert-impresso-mediasources-ner` | Model weights, tokenizer, `config.json`, `README.md`, `pipeline.py`, `requirements.txt` |

### Source Copies In Workbench

Keep source versions in the workbench:

```text
hf_dataset/README.md
hf_testset/README.md
hf_model/README.md
hf_model/pipeline.py
hf_model/requirements.txt
```

Publishing scripts copy these into the appropriate HF repos. Do not edit cards or pipeline code only in `hub/*`; those submodules are for inspection and pinned revision awareness.

### Publishing Tasks

- [ ] Add `hub/impresso-mediaagencies-ner-dataset` as a submodule pointing to the HF training dataset repo.
- [ ] Add `hub/newsagency-radiostation-testset` as a submodule pointing to the HF testset repo.
- [ ] Add `hub/mmbert-impresso-mediasources-ner` as a submodule pointing to the HF model repo.
- [ ] Implement `lib.publish_dataset` with dry-run preflights.
- [ ] Implement `lib.publish_testset` with stronger frozen-testset checks.
- [ ] Implement `lib.push_model_to_hub` with model payload preflights.
- [ ] Make publishing fail if labels do not match canonical metadata in `resources/newsagency_seeds.json` and `resources/radiostation_seeds.json`.
- [ ] Make model publishing fail if `config.json`, label map, tokenizer files, model weights, model card, requirements, or pipeline code are missing.
- [ ] Add a smoke comparison between local inference and `hf_model/pipeline.py`.
- [ ] Record published HF commit SHAs in release configs and model config.

### Public Commands

The public command index should live in `Makefile` and expose stable targets:

```bash
make help
make sample-newsagencies ARGS="--dry-run --max-docs 10"
make sample-radiostations ARGS="--dry-run --max-docs 10"
make curate ARGS="--input data/candidates/newsagencies.jsonl"
make export-dataset
make publish-dataset ARGS="--dry-run"
make publish-testset ARGS="--dry-run"
make train CFG=configs/model-v0.1.0.mk
make test CFG=configs/model-v0.1.0.mk
make test-official CFG=configs/model-v0.1.0.mk
make push-model CFG=configs/model-v0.1.0.mk
make smoke
```

## Pipeline Integration

The symlinked `impresso-pipelines` repository contains the current older news-agency pipeline:

```text
impresso-pipelines/
  impresso_pipelines/newsagencies/
    newsagencies_pipeline.py
    config.py
  tests/newsagencies/test_newsagenies_pipeline.py
  README_newsagencies.md
```

Relevant behavior from the existing pipeline:

- Public class: `impresso_pipelines.newsagencies.NewsAgenciesPipeline`.
- Default HF model: `impresso-project/ner-newsagency-bert-multilingual`.
- Core model wrapper: `NewsAgencyTokenClassifier`.
- HF-style pipeline: `ChunkAwareTokenClassification`.
- Dependencies for this extra: `transformers`, `torch`, and `torchvision`.
- Input: one string or a list of strings.
- Default output: JSON-like summaries under `{"agencies": [...]}` with `uid`, `relevance`, and `wikidata_link`.
- Diagnostics output: entity-level JSON with `surface`, `start`, `stop`, `relevance`, and `uid`.
- Chunking uses tokenizer overflow windows, `stride=64`, and offset mappings.
- It suppresses `org.ent.pressagency.unk`, `ag`, and `pers.ind.articleauthor` by default.
- `config.py` contains an `AGENCY_LINKS` map to Wikidata URLs for the old label set.

This is the best starting point for the new simple Hugging Face pipeline. The new workbench should adapt it rather than reintroducing TorchServe.

Pipeline migration tasks:

- [ ] Add `pipeline/impresso-pipelines` as a submodule or symlink reference in the new workbench.
- [ ] Port `NewsAgenciesPipeline` into `hf_model/pipeline.py` as a self-contained HF model pipeline.
- [ ] Rename public semantics from `NewsAgenciesPipeline` to a joint news-agency/radio-station pipeline, while keeping a compatibility alias if needed.
- [ ] Replace hard-coded `AGENCY_LINKS` with metadata loaded from the published model or dataset artifact.
- [ ] Extend output keys beyond `agencies` so radio-station hits are represented without ambiguity.
- [ ] Keep JSON output as the only required inference format.
- [ ] Preserve diagnostics fields: `surface`, `start`, `stop`, `uid`, `entity_type`, `relevance`, and metadata links.
- [ ] Keep suppression for `unk`, unresolved bare `ag`, and `pers.ind.articleauthor`.
- [ ] Add suppression/configuration support by full label and by entity family.
- [ ] Add tests for one input string, batched input, diagnostics output, repeated mentions, and punctuation-adjacent offsets.
- [ ] Ensure the HF model repo can run inference without importing from the workbench or from `impresso-pipelines`.

## Provenance Requirements

Every published model must have a `config.json` that answers:

- Which base model was fine-tuned?
- Which label vocabulary was used?
- Which exact HF training dataset revision was used?
- Which exact HF testset revision was used?
- Which hyperparameters were used?
- Which official metrics were recorded?
- Which pipeline code version was published?

Example shape:

```json
{
  "model_type": "modernbert-token-classifier",
  "base_model": "jhu-clsp/mmBERT-base",
  "labels": {
    "0": "O",
    "1": "B-org.ent.pressagency.reuters",
    "2": "I-org.ent.pressagency.reuters",
    "3": "B-org.ent.radiostation.bbc",
    "4": "I-org.ent.radiostation.bbc"
  },
  "training": {
    "dataset_source": "hf:impresso-project/impresso-mediaagencies-ner-dataset@<sha>",
    "hyperparameters": {
      "epochs": 3,
      "batch_size": 16,
      "max_sequence_len": 512,
      "seed": 42
    }
  },
  "evaluation": {
    "official_testset": "hf:impresso-project/newsagency-radiostation-testset@<sha>",
    "metrics": {
      "precision": null,
      "recall": null,
      "f1": null
    }
  }
}
```

Do not invent provenance for legacy checkpoints. If an old checkpoint is used for comparison, document missing provenance explicitly and require strict provenance for new publishable models.

## Migration Sequence

1. Freeze this current sampler repo as the source reference.
2. Create the new workbench repository with the layout above.
3. Move current sampler scripts into `lib/` with CLI wrappers and tests.
4. Convert current resources into normalized seed/candidate files.
5. Create the training-code repository and add it as a submodule.
6. Migrate modernBERT-only training code from Nikki's repo into the training submodule.
7. Define and test the joint news-agency/radio-station annotation guidelines and canonical metadata policy.
8. Export a first curated JSONL dataset from accepted news-agency and radio-station material.
9. Publish the training dataset and record the HF commit SHA.
10. Freeze and publish an official held-out testset.
11. Train the first provenance-complete model from `configs/model-v0.1.0.mk`.
12. Evaluate against the official testset and write metrics into model config.
13. Publish model weights, tokenizer/config, card, requirements, and self-contained pipeline code to the HF model repo.
14. Add smoke tests that load the published model pipeline and run a tiny example.

## Remaining Open Decisions

- Final repository name.
- Final HF repository names.
- Exact canonical radio-station label list and normalization scheme.
- Whether Wikipedia links should use English Wikipedia only or language-specific pages when available.
- Whether the pipeline should return one flat `entities` list only, or both `entities` and grouped summaries such as `agencies` and `radio_stations`.
