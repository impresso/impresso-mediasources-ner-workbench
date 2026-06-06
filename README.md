# Impresso Media Sources NER Workbench

Workbench for searching, sampling, curating, training, evaluating, and publishing a joint Impresso media-source NER model for news agencies and radio stations.

The workbench follows the control-plane pattern used by `impresso-frakturline-classifier-workbench`: code, curation tools, release configs, tests, and source Hugging Face cards live here; published datasets, test sets, and model payloads live on Hugging Face.

## Scope

- One joint token-classification model.
- News-agency labels: `org.ent.pressagency.<canonical_id>`.
- Radio-station labels: `org.ent.radiostation.<canonical_id>`.
- Training data format: JSONL text/span records.
- Inference output format: JSONL with offsets and provenance.
- Deployment path: simple Hugging Face pipeline, no TorchServe for the initial implementation.

For a high-level view of the workbench activities and their sub-workflows, see [docs/workflows.md](docs/workflows.md).

Terminology: **HIPE-derived data** refers to the converted French/German news-agency annotations imported from the earlier HIPE/CoNLL-style source files. It is still active baseline training and evaluation data. Some paths, commands, and trace-back fields keep `legacy-*` names for compatibility.

## Repository Map

```text
configs/       Release configs for publishable model runs
lib/           Sampling, curation, export, publish, and pipeline helpers
resources/     Canonical label metadata and curation policy
data/          Local candidates, curated data, and held-out test data
hf_dataset/    Source training dataset card
hf_testset/    Source testset card
hf_model/      Source model card, requirements, and pipeline code
hub/           Future Hugging Face repo submodules
training/      Future training-code submodule
pipeline/      Future impresso-pipelines reference
tests/         Fixtures and contract tests
```

## Installation

Use Python 3.11 or newer.

```bash
cd impresso-mediasources-ner-workbench
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For Hugging Face publishing or model work, install the optional HF dependencies:

```bash
python -m pip install -e ".[dev,hf]"
python -m pip install -e training/newsagency-radiostation-modernbert-classifier
```

Workbench commands use a local Hugging Face cache by default:

```text
HF_HOME=hf.d
```

Override `HF_HOME` on the command line if you want to reuse another cache.
If `HF_TOKEN` is set in the workbench `.env`, Hugging Face scoring, training, and publishing commands load it automatically.

Local generated directory roots use the `*.d` suffix convention. Defaults include `hf.d/`, `mlm.d/`, `models.d/`, and `staging.d/`; these are ignored by git. See [GENERATED_DIRS.md](GENERATED_DIRS.md) for the convention.

For Impresso API sampling workflows, install the sampling extras:

```bash
python -m pip install -e ".[dev,sampling]"
```

After installation, run the lightweight checks:

```bash
make smoke
python tests/test_import_legacy_hipe_tsv.py
```

To test the HIPE-derived data converter on the fixture:

```bash
make import-legacy-hipe ARGS="--input tests/fixtures/legacy_hipe_sample.tsv --source-root . --split validation --output /private/tmp/mediasources-fixture --newsagency-seeds resources/newsagency_seeds.json"
```

## Training

First create the cleaned HIPE-derived JSONL dataset:

```bash
make import-legacy-hipe ARGS="--input ../newsagency-classification-main-nikki/data/annotated_data/de --input ../newsagency-classification-main-nikki/data/annotated_data/fr --source-root ../newsagency-classification-main-nikki --output data/curated/legacy-import --newsagency-seeds resources/newsagency_seeds.json --forbidden-label-policy exclude --unknown-label-policy error --malformed-bio-policy error --duplicate-policy keep-first"
```

Optionally download the compiled Impresso source files for continued MLM pretraining:

```bash
make download-mlm-sources PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

The source URLs are configured in `configs/model-v0.1.0.mk` as `MLM_SOURCE_URL_DE`, `MLM_SOURCE_URL_FR`, `MLM_SOURCE_URL_EN`, and `MLM_SOURCE_URL_LB`. Files are written to `mlm.d/source/` by default, unless you override `MLM_DATASET_DIR`.

Then build the multilingual MLM corpus. By default this samples up to 300,000 texts per language, exhausting smaller languages such as Luxembourgish, and keeps 1 percent for validation:

```bash
make build-mlm-data PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

Then continue MLM pretraining from `jhu-clsp/mmBERT-base` to create `models.d/multilingualmodernimpressoBERT_v0.1.0/final`:

```bash
make pretrain-mlm PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

The default MLM run keeps the sampled corpus on disk but trains on `MLM_MAX_TRAIN_SAMPLES=100000` rows and evaluates on `MLM_MAX_EVAL_SAMPLES=2000` rows. It uses one epoch, `MLM_MAX_LEN=256`, fixed max-length padding, `MLM_BATCH=1`, `MLM_GRADIENT_ACCUMULATION_STEPS=8`, gradient checkpointing, learning rate `2e-5`, weight decay `0.01`, and automatic warmup over 6 percent of the capped optimizer steps. Validation runs three times across the epoch plus one final evaluation. Intermediate checkpoint saving is disabled by default; the final model is always saved to `models.d/multilingualmodernimpressoBERT_v0.1.0/final`. Override these on the command line to match available GPU memory or to run a smaller smoke test.

MLM tokenization pads to the configured max length by default to keep tensor shapes stable on Apple MPS, and caches the tokenized dataset under `mlm.d/tokenized_multilingual_max300k_per_lang_len256_padded` by default. Delete that directory or override `MLM_TOKENIZED_CACHE_DIR` if you change tokenization-relevant settings such as `MLM_MAX_LEN` or `MLM_PAD_TO_MAX_LENGTH`.

Push the continued-MLM checkpoint and source model card to Hugging Face:

```bash
make push-mlm-model PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

Then train the media-source NER model. The default base model in `configs/model-v0.1.0.mk` is the pushed continued-MLM checkpoint `hf://impresso-project/mmbert-multilingual-impresso-continued-mlm`.

```bash
make train PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

Local Apple MPS training uses memory-conservative defaults: `BATCH=1`, `GRADIENT_ACCUMULATION_STEPS=4`, gradient checkpointing, `OPTIMIZER=adafactor`, and `FREEZE_BASE_MODEL=true`. This trains the token-classification head on top of the adapted encoder. Use `FREEZE_BASE_MODEL=false` only on hardware with enough memory for full-model optimizer updates.

Validation is run after each epoch for early stopping. The default monitors `entity_f1` with `EARLY_STOPPING_PATIENCE=1` and writes the best checkpoint to `models.d/newsagency_radiostation_modernbert_v0.1.0/best`.

At startup, training prints and writes `training_start_report.json` with the model source, device, optimizer, trainable/frozen parameter counts, batch and window settings, early-stopping configuration, and train/validation dataset summaries. During validation and test evaluation, the trainer prints a compact NER summary with exact entity precision/recall/F1, non-`O` token precision/recall/F1, token accuracy, and the most frequent gold/predicted entity labels. The full metrics and prediction JSONL files are still written under the model output directory.

To continue from an existing classifier checkpoint, pass `CHECKPOINT`. This loads the model weights but starts a fresh optimizer state, so use a lower learning rate for continuation runs. Prefer writing to a new `MODEL` directory unless you intentionally want to overwrite the previous output:

```bash
make train PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk CHECKPOINT=models.d/newsagency_radiostation_modernbert_v0.1.0/best MODEL=models.d/newsagency_radiostation_modernbert_v0.1.0_continue1 EPOCHS=2 LEARNING_RATE=1e-5
```

Select another base model on the command line when needed:

```bash
make train PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk BASE_MODEL=models.d/multilingualmodernimpressoBERT_v0.1.0/final
make train PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk BASE_MODEL=hf://impresso-project/mmbert-multilingual-impresso-continued-mlm
make train PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk BASE_MODEL=jhu-clsp/mmBERT-base MODEL=models.d/newsagency_radiostation_mmbert_base_v0.1.0
```

For a quick one-step smoke test:

```bash
make train PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk ARGS="--max-steps 1 --device cpu --epochs 1 --train-batch-size 1 --eval-batch-size 1 --max-words-per-window 64 --stride-words 0 --output-dir /private/tmp/mediaagency-modernbert-smoke"
```

After training, evaluate consistency against validation and test:

```bash
make test PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
make test-official PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

Metrics and prediction JSONL files are written under `models.d/newsagency_radiostation_modernbert_v0.1.0/eval/`.

For basic curation of the existing HIPE-derived French/German dev and test folds, run the selected model over both splits and build disagreement records for manual review:

```bash
make curate-legacy-eval PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk CURATION_MODEL=models.d/newsagency_radiostation_modernbert_v0.1.0_continue1/best
```

To build only one fold's review queue, use `make curate-legacy-validation ...` or `make curate-legacy-test ...` with the same arguments. The command names keep `legacy` for compatibility; the data itself is the active HIPE-derived baseline, not discarded material.

The review files are written below `data/curated/legacy-eval-curation/review/`, including split/language files such as `validation_de_disagreements.jsonl`, `validation_fr_disagreements.jsonl`, `test_de_disagreements.jsonl`, and `test_fr_disagreements.jsonl`. Each row contains a deterministic `review_id`, document metadata, gold entity, predicted entity, token context, and a `decision` block for manual curation.

For iterative or multi-reviewer curation, store decisions in `data/curated/legacy-eval-curation/review/decisions.jsonl` and regenerate the review files. Rows with a matching `review_id` are marked with the saved decision, and remaining items are written to `todo_disagreements.jsonl`.

To test a short terminal curation session:

```bash
make review-curation PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk REVIEWER="$USER" ARGS="--limit 1"
make curation-review PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
make validate-curation PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk ARGS=--no-require-complete
```

The reviewer appends to `decisions.jsonl`; it does not modify the generated disagreement files.

Before committing curation decisions, validate that every current disagreement has exactly one completed decision:

```bash
make curation-review PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
make validate-curation PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

Use `ARGS=--no-require-complete` only for in-progress review snapshots.

After validation, apply the reviewed decisions to a new curated JSONL directory:

```bash
make apply-curation PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

This writes revised HIPE-derived folds to `data/curated/legacy-import-curated/` and leaves the original `data/curated/legacy-import/` files untouched. The output includes `train.jsonl`, `validation.jsonl`, `test.jsonl`, `label_map.json`, `curation_changes.jsonl`, `curation_changes_tags.tsv`, and `curation_summary.json`. Boundary corrections are parsed from notes such as `13:15 "Agence Wolff" label=org.ent.pressagency.wolff`.

To inspect the exact ground-truth changes before publishing or retraining, compare the original and curated JSONL files with `git diff --no-index`:

```bash
git diff --no-index data/curated/legacy-import/validation.jsonl data/curated/legacy-import-curated/validation.jsonl
git diff --no-index data/curated/legacy-import/test.jsonl data/curated/legacy-import-curated/test.jsonl
git diff --no-index data/curated/legacy-import/label_map.json data/curated/legacy-import-curated/label_map.json
```

For a decision-level audit, inspect `data/curated/legacy-import-curated/curation_changes.jsonl`. Decisions marked as `ignored` are documented there and leave the corresponding annotation unchanged for this curation pass.

For a lightweight NER-tag overview, inspect `data/curated/legacy-import-curated/curation_changes_tags.tsv`. It is a CoNLL-like TSV grouped by review item, with comments followed by `TOKEN`, `BEFORE_NERTAG`, and `AFTER_NERTAG` columns. Context comments and review displays use the HIPE `NoSpaceAfter` render metadata where available, so abbreviations and elisions appear in natural form such as `D.N.B.` or `l'Agence`, not as whitespace-joined token strings.

The fine-tuned Hugging Face model repository is configured as `HF_MODEL=impresso-project/mmbert-impresso-mediasources-ner`. The v0.1 label space covers news agencies and radio stations; the repository name leaves room for future cited media-source families such as newspaper citations.

```bash
make push-model PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk MODEL=models.d/newsagency_radiostation_modernbert_v0.1.0_continue1/best
```

## Common Commands

```bash
make help
make smoke
make validate-labels
make sample-newsagencies ARGS="--dry-run --labels org.ent.pressagency.reuters --max-queries-per-label 1"
make sample-radiostations ARGS="--dry-run --labels org.ent.radiostation.rtl --max-queries-per-label 1"
make export-dataset
make download-mlm-sources
make build-mlm-data
make pretrain-mlm
make push-mlm-model
make publish-dataset ARGS="--dry-run"
make publish-testset ARGS="--dry-run"
make train CFG=configs/model-v0.1.0.mk
make test CFG=configs/model-v0.1.0.mk
make apply-curation CFG=configs/model-v0.1.0.mk
make score-newsagency-snippets CFG=configs/model-v0.1.0.mk
make review-newsagency-snippets CFG=configs/model-v0.1.0.mk REVIEWER="$USER"
make export-newsagency-snippets CFG=configs/model-v0.1.0.mk
make score-radiostation-snippets CFG=configs/model-v0.1.0.mk
make review-radiostation-spans CFG=configs/model-v0.1.0.mk REVIEWER="$USER"
make export-radiostation-snippets CFG=configs/model-v0.1.0.mk
make push-model CFG=configs/model-v0.1.0.mk
```

For Impresso API sampling, the token is entered interactively when the sampler connects. Do not put the token in `.env`.

You can create a local `.env` for non-secret Impresso API settings and optional Hugging Face authentication:

```bash
cp .env.example .env
```

By default `IMPRESSO_PERSISTED_TOKEN=false`, so the `impresso` client prompts for the Impresso API token and does not write it to `~/.impresso_py.yml`. Set it to `true` only if you intentionally want the client to reuse/store its persisted token outside this repository. `.env` is gitignored.

## Publish Dataset

The training dataset publisher prepares a Hugging Face-ready directory from the curated JSONL without uploading by default:

```bash
make publish-dataset PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk
```

By default this reads `data/curated/legacy-import-curated/` and writes `staging.d/datasets/impresso-mediaagencies-ner-dataset/` with:

```text
README.md
data/train.jsonl
data/validation.jsonl
data/test.jsonl
label_map.json
dataset_summary.json
audit/curation_summary.json
audit/curation_changes.jsonl
audit/curation_changes_tags.tsv
```

The publisher validates entity labels against `resources/newsagency_seeds.json` and `resources/radiostation_seeds.json`. To upload after inspecting the staged directory:

```bash
make publish-dataset PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk ARGS="--upload"
```

The staged `data/*.jsonl` files are compact public training files, not byte-for-byte copies of the converted HIPE import. They keep the useful model/data fields (`text`, `tokens`, token offsets, BIO labels, entity spans, document metadata, quality flags) and group only minimal trace-back fields under `legacy`. In that field name, `legacy` means HIPE import trace-back metadata retained for compatibility, not data that is obsolete. Large conversion/debug fields such as `segments`, `sentences`, `token_nel`, `token_ocr`, `token_render`, and `token_segment_ids` stay in the local curated source unless explicitly needed for an audit workflow.

To open a Hub pull request instead of pushing directly:

```bash
make publish-dataset PYTHON=.venv/bin/python CFG=configs/model-v0.1.0.mk ARGS="--upload --create-pr"
```

Most commands are scaffolded and will become active as the implementation lands.

## State Summaries

Use these targets to check local curation progress and dataset staging state:

```bash
make curation-state CFG=configs/model-v0.1.0.mk
make snippet-state CFG=configs/model-v0.1.0.mk
make legacy-curation-state CFG=configs/model-v0.1.0.mk
make dataset-state CFG=configs/model-v0.1.0.mk
make curation-state-json CFG=configs/model-v0.1.0.mk
```

`curation-state-json` writes `staging.d/reports/curation_state.json` by default. To check the Hugging Face dataset repository over the network, pass `ARGS="--fetch-published"` to `dataset-state` or `curation-state`.

## Language-Aware Coverage

Coverage and targeted sampling are label-language aware. By default, `de`, `fr`, and `en` are main languages with a target of 20 accepted examples per label and language; `lb` and `it` are side languages with a target of 5. The default sampler language lists follow these configured main and side languages.

```bash
make annotation-stats CFG=configs/model-v0.1.0.mk
make sample-needed-newsagencies CFG=configs/model-v0.1.0.mk
make sample-radiostations CFG=configs/model-v0.1.0.mk RADIOSTATION_SAMPLE_ONLY_UNDER_TARGET=true
```

Override the defaults from the command line when needed:

```bash
make annotation-stats CFG=configs/model-v0.1.0.mk ANNOTATION_MAIN_LANGS="de fr en" ANNOTATION_SIDE_LANGS="lb it" ANNOTATION_MAIN_TARGET_PER_LABEL_LANG=20 ANNOTATION_SIDE_TARGET_PER_LABEL_LANG=5
make annotation-stats CFG=configs/model-v0.1.0.mk ANNOTATION_LANGUAGE_TARGETS="de=30 fr=30 en=20 lb=8 it=8"
```

## Plan

See [WORKBENCH_PLAN.md](WORKBENCH_PLAN.md) for the implementation plan and thesis-derived requirements.

See [docs/annotation_guidelines.md](docs/annotation_guidelines.md) for the news-agency and radio-station annotation rules.

See [docs/curation.md](docs/curation.md) for the HIPE-derived dev/test curation and review workflow.

See [docs/jsonl_schema.md](docs/jsonl_schema.md) for the annotated JSONL field contract and its mapping from the HIPE TSV CoNLL-style format.

See [docs/hipe_to_jsonl_conversion_plan.md](docs/hipe_to_jsonl_conversion_plan.md) for the concrete conversion workflow from the original HIPE data into the new JSONL dataset.

See [GENERATED_DIRS.md](GENERATED_DIRS.md) for the local generated-directory convention.
