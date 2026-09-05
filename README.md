# Impresso Media Sources NER Workbench

Workbench for searching, sampling, curating, training, evaluating, and publishing a joint Impresso media-source NER model for news agencies and radio stations.

This repository is about three core workflows:

- **Audit** existing annotated data to find missed spans, false negatives, boundary issues, or inconsistent labels, then patch accepted corrections back into a prerelease.
- **Sample** new material from Impresso to improve label/language coverage or add examples for newly scoped entity families.
- **Review** pre-annotated material through append-only human decisions, turning audit candidates or sampled candidates into curated training data.

In short:

```text
audit existing data -> review suspicious patches -> update prerelease
sample new material -> pre-annotate -> review candidates -> update prerelease
```

The workbench follows the control-plane pattern used by `impresso-frakturline-classifier-workbench`: code, curation tools, release configs, tests, and source Hugging Face cards live here; published datasets, test sets, and model payloads live on Hugging Face.

## Released Versions

### v2.0.0

Dataset and model v2.0.0 were released in August 2026.

**Dataset**

- Repository: `impresso-project/impresso-mediaagencies-ner-dataset`
- Revision: `v2.0.0`
- Hugging Face commit: `a7ac5dc1ec0dd92ae848dbccd258aa0361830da3`
- Git release snapshot: `data/releases/dataset-v2.0.0/`
- Published dataset was verified against the Git release using the public-projection comparison workflow.

**Model**

- Repository: `impresso-project/mmbert-impresso-mediasources-ner`
- Revision: `v2.0.0`
- Hugging Face commit: `9899ad960b9bc310ee51cd7ee658fd3882b6b140`
- Base model: `impresso-project/mmbert-multilingual-impresso-continued-mlm`
- Selected-checkpoint validation entity F1: `0.9285`
- Held-out test entity F1: `0.8981`
- Decoder: `first_subtoken_viterbi`
- Runtime inference parity: `458/458` held-out test documents matched evaluator decoded BIO sequences exactly; reproduced `529/612/566` exact entities and test F1 `0.8981324278`.

The released model was trained from the pinned published v2.0.0 dataset. Runtime parity was validated with the downloaded v2.0.0 model artifact and the v2.0.0 Git release test split. Detailed model provenance is recorded in `hf_model/model_provenance.json`.

## Scope

- One joint token-classification model.
- News-agency labels: `org.ent.pressagency.<canonical_id>`.
- Radio-station labels: `org.ent.radiostation.<canonical_id>`.
- Training data format: JSONL text/span records.
- Inference output format: JSONL with offsets and provenance.
- Deployment path: simple Hugging Face pipeline, no TorchServe for the initial implementation.

For a high-level view of the workbench activities and their sub-workflows, see [docs/workflows.md](docs/workflows.md).

Dataset growth has two explicit axes. **Horizontal extension** adds more documents/examples for existing labels. **Vertical extension** deepens annotations in existing documents by adding more entity types, such as future newspaper mentions. Keep these separate in audit, review, and release notes. See [DATASET_EXTENSION_PLAN.md](DATASET_EXTENSION_PLAN.md).

Terminology: **HIPE-derived data** refers to the converted French/German news-agency annotations imported from the earlier HIPE/CoNLL-style source files. It is still active baseline training and evaluation data. Some local paths and trace-back fields still use `legacy` because they describe retained import provenance, not obsolete data.

## Repository Map

```text
configs/       Release configs for publishable model runs
lib/           Sampling, curation, export, publish, and pipeline helpers
resources/     Canonical label metadata and curation policy
data/          Local candidates, curated data, and held-out test data
data/releases/ Committed dataset release snapshots
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

Local working data under `data/candidates/`, `data/curated/`, and `data/testset/` is ignored. Shared dataset prerelease snapshots belong under `data/prereleases/<dataset-version>/`; published release snapshots belong under `data/releases/<dataset-version>/`. Both are committed. See [docs/data_lifecycle.md](docs/data_lifecycle.md).

Release configs are version-scoped. `configs/model-v1.0.0.mk` points at the published press-agency baseline release. `configs/model-v2.0.0.mk` is the active prerelease config for press agencies plus radio stations and is the default. `configs/model-v0.1.0.mk` is retained only for historical v0.1 runs.

For Impresso API sampling workflows, install the sampling extras:

```bash
python -m pip install -e ".[dev,sampling]"
```

After installation, run the lightweight checks:

```bash
make smoke
python tests/test_import_legacy_hipe_tsv.py
```

Command examples in this file assume the virtual environment is activated (`source .venv/bin/activate`) and the default release config `CFG=configs/model-v2.0.0.mk` is in effect. Pass `CFG=` or `PYTHON=` only when you need a non-default value. See [docs/curation.md](docs/curation.md) for the full curation workflow and command assumptions.

To test the HIPE-derived data converter on the fixture:

```bash
make import-hipe ARGS="--input tests/fixtures/legacy_hipe_sample.tsv --source-root . --split validation --output /private/tmp/mediasources-fixture --newsagency-seeds resources/newsagency_seeds.json"
```

## Training

First create the cleaned HIPE-derived JSONL dataset:

```bash
make import-hipe ARGS="--input ../newsagency-classification-main-nikki/data/annotated_data/de --input ../newsagency-classification-main-nikki/data/annotated_data/fr --source-root ../newsagency-classification-main-nikki --output data/curated/legacy-import --newsagency-seeds resources/newsagency_seeds.json --forbidden-label-policy exclude --unknown-label-policy error --malformed-bio-policy error --duplicate-policy keep-first"
```

Optionally download the compiled Impresso source files for continued MLM pretraining:

```bash
make download-mlm-sources
```

The source URLs are configured in `configs/model-v2.0.0.mk` as `MLM_SOURCE_URL_DE`, `MLM_SOURCE_URL_FR`, `MLM_SOURCE_URL_EN`, and `MLM_SOURCE_URL_LB`. Files are written to `mlm.d/source/` by default, unless you override `MLM_DATASET_DIR`.

Then build the multilingual MLM corpus. By default this samples up to 300,000 texts per language, exhausting smaller languages such as Luxembourgish, and keeps 1 percent for validation:

```bash
make build-mlm-data
```

Then continue MLM pretraining from `jhu-clsp/mmBERT-base` to create `models.d/multilingualmodernimpressoBERT_v1.0.0/final`:

```bash
make pretrain-mlm
```

The default MLM run keeps the sampled corpus on disk but trains on `MLM_MAX_TRAIN_SAMPLES=100000` rows and evaluates on `MLM_MAX_EVAL_SAMPLES=2000` rows. It uses one epoch, `MLM_MAX_LEN=256`, fixed max-length padding, `MLM_BATCH=1`, `MLM_GRADIENT_ACCUMULATION_STEPS=8`, gradient checkpointing, learning rate `2e-5`, weight decay `0.01`, and automatic warmup over 6 percent of the capped optimizer steps. Validation runs three times across the epoch plus one final evaluation. Intermediate checkpoint saving is disabled by default; the final model is always saved to `models.d/multilingualmodernimpressoBERT_v1.0.0/final`. Override these on the command line to match available GPU memory or to run a smaller smoke test.

MLM tokenization pads to the configured max length by default to keep tensor shapes stable on Apple MPS, and caches the tokenized dataset under `mlm.d/tokenized_multilingual_max300k_per_lang_len256_padded` by default. Delete that directory or override `MLM_TOKENIZED_CACHE_DIR` if you change tokenization-relevant settings such as `MLM_MAX_LEN` or `MLM_PAD_TO_MAX_LENGTH`.

Push the continued-MLM checkpoint and source model card to Hugging Face:

```bash
make push-mlm-model
```

Then train the media-source NER model. The default base model in `configs/model-v2.0.0.mk` is the pushed continued-MLM checkpoint `hf://impresso-project/mmbert-multilingual-impresso-continued-mlm`.

```bash
make train
```

Local Apple MPS training uses memory-conservative defaults: `BATCH=1`, `GRADIENT_ACCUMULATION_STEPS=4`, gradient checkpointing, `OPTIMIZER=adafactor`, `FREEZE_BASE_MODEL=true`, and `UNFREEZE_TOP_LAYERS=3`. This trains the token-classification head plus the top encoder layers. Use `FREEZE_BASE_MODEL=false` only on hardware with enough memory for full-model optimizer updates.

Validation is run after each epoch for early stopping. The default monitors `entity_f1` with `EARLY_STOPPING_PATIENCE=2` and writes the best checkpoint to `models.d/newsagency_radiostation_modernbert_v2.0.0/best`.

At startup, training prints and writes `training_start_report.json` with the model source, workbench Git commit/dirty status, device, optimizer, trainable/frozen parameter counts, batch and window settings, early-stopping configuration, and train/validation dataset summaries. During validation and test evaluation, the trainer prints a compact NER summary with exact entity precision/recall/F1, non-`O` token precision/recall/F1, token accuracy, and the most frequent gold/predicted entity labels. The full metrics and prediction JSONL files are still written under the model output directory.

To continue from an existing classifier checkpoint, pass `CHECKPOINT`. This loads the model weights but starts a fresh optimizer state, so use a lower learning rate for continuation runs. Prefer writing to a new `MODEL` directory unless you intentionally want to overwrite the previous output:

```bash
make train CHECKPOINT=models.d/newsagency_radiostation_modernbert_v2.0.0/best MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1 EPOCHS=2 LEARNING_RATE=1e-5
```

Select another base model on the command line when needed:

```bash
make train BASE_MODEL=models.d/multilingualmodernimpressoBERT_v1.0.0/final
make train BASE_MODEL=hf://impresso-project/mmbert-multilingual-impresso-continued-mlm
make train BASE_MODEL=jhu-clsp/mmBERT-base MODEL=models.d/newsagency_radiostation_mmbert_base_v2.0.0
```

For a quick one-step smoke test:

```bash
make train ARGS="--max-steps 1 --device cpu --epochs 1 --train-batch-size 1 --eval-batch-size 1 --max-words-per-window 64 --stride-words 0 --output-dir /private/tmp/mediaagency-modernbert-smoke"
```

After training, evaluate consistency against validation and test:

```bash
make test
make test-official
```

Metrics and prediction JSONL files are written under `models.d/newsagency_radiostation_modernbert_v2.0.0/eval/`.

### Decoder And Supervision Experiment

The `decoding-v2.0.0` experiment compares two subtoken-supervision regimes across three random seeds and four validation-time decoders. This is a validation-only model-selection experiment; the held-out test set is intentionally not part of the matrix.

```bash
make decoding-experiment-plan CFG=configs/experiments/decoding-v2.0.0.mk
make decoding-experiment-train CFG=configs/experiments/decoding-v2.0.0.mk
make decoding-experiment-evaluate CFG=configs/experiments/decoding-v2.0.0.mk
make decoding-experiment-report CFG=configs/experiments/decoding-v2.0.0.mk
```

The factorial design is:

- training supervision: `first_subtoken`, `all_subtokens_b_to_i`
- seeds: `17`, `42`, `73`
- validation decoders: `first_subtoken`, `first_subtoken_viterbi`, `all_subtoken`, `all_subtoken_viterbi`
- checkpoint-selection decoder during training: `first_subtoken_viterbi`

Validation results:

| Training supervision | Decoder | Runs | Entity F1 mean | F1 stdev | Precision mean | Recall mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `all_subtokens_b_to_i` | `all_subtoken` | 3 | 0.909749 | 0.009852 | 0.923324 | 0.896636 |
| `all_subtokens_b_to_i` | `all_subtoken_viterbi` | 3 | 0.931488 | 0.005875 | 0.953285 | 0.910703 |
| `all_subtokens_b_to_i` | `first_subtoken` | 3 | 0.909763 | 0.012638 | 0.920152 | 0.899694 |
| `all_subtokens_b_to_i` | `first_subtoken_viterbi` | 3 | 0.934203 | 0.006402 | 0.952969 | 0.916208 |
| `first_subtoken` | `all_subtoken` | 3 | 0.837113 | 0.011675 | 0.895949 | 0.785933 |
| `first_subtoken` | `all_subtoken_viterbi` | 3 | 0.862078 | 0.018103 | 0.934897 | 0.800000 |
| `first_subtoken` | `first_subtoken` | 3 | 0.895961 | 0.008436 | 0.907963 | 0.884404 |
| `first_subtoken` | `first_subtoken_viterbi` | 3 | 0.921399 | 0.002280 | 0.944217 | 0.899694 |

The four decoder settings differ in how model subtokens are converted back to annotation-token predictions. `first_subtoken` decoders use only the first model subtoken as word-level evidence, while `all_subtoken` decoders aggregate evidence from all model subtokens belonging to an annotation token. The `_viterbi` variants additionally enforce the BIO sequence constraints.

These post-release validation experiments support the supervision and decoding choices used by the released v2.0.0 model and establish the preferred protocol for subsequent training runs. The strongest validation setting is `all_subtokens_b_to_i` training with `first_subtoken_viterbi` decoding: mean entity F1 `0.934203`.

Decoder ablation makes the trade-off explicit. With the selected all-subtoken B-to-I supervision, raw first-subtoken argmax costs about 2.4 validation F1 points compared with `first_subtoken_viterbi`. The unconstrained `all_subtoken` argmax decoder performs similarly to raw first-subtoken argmax. `all_subtoken_viterbi` is close under all-subtoken supervision, but does not improve over `first_subtoken_viterbi`. With first-subtoken-only supervision, continuation subtokens are not trained as word-level label evidence, and consuming those positions during all-subtoken decoding substantially degrades performance. Decoder and supervision choices therefore cannot be considered independently.

The simpler `first_subtoken` training setup with `first_subtoken_viterbi` decoding also works reasonably well, reaching mean validation entity F1 `0.921399`. It is not the selected v2 release protocol, but it remains a useful lower-complexity baseline when comparing future supervision strategies.

### Context Width Experiments

The context experiments use the selected supervision and decoder and remain validation-only. They measure whether larger training or inference window configurations improve the selected protocol. Because maximum sequence length, words per window, and stride scale together, these experiments compare window configurations rather than isolating sequence length as a single causal factor.

Matched train/inference context results:

| Context | Max sequence | Max words | Stride | Runs | Entity F1 mean | F1 stdev | Precision mean | Recall mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ctx512` | 512 | 256 | 32 | 3 | 0.934203 | 0.006402 | 0.952969 | 0.916208 |
| `ctx1024` | 1024 | 512 | 64 | 3 | 0.932313 | 0.003509 | 0.951101 | 0.914373 |
| `ctx2048` | 2048 | 1024 | 128 | 3 | 0.926514 | 0.003103 | 0.943580 | 0.910092 |

A separate `context-inference-v2.0.0` matrix evaluated already trained 512-, 1024-, and 2048-context models under 512, 1024, and 2048 inference windows. The crossed train/inference matrix separates the effect of training with longer windows from the effect of merely presenting longer windows at inference. Increasing inference context did not improve performance for the longer-context models, and the 512-trained model also did not benefit from larger inference windows. Mean validation entity F1 ranged from `0.924440` to `0.934203`, so quality remained reasonably stable across the tested window configurations. The default `512/256/32` window is therefore the best validation setting and the most efficient conservative deployment choice.

### Layer Adaptation Experiment

The `layers-v2.0.0` experiment keeps the best 512-context protocol fixed and varies only the number of unfrozen top ModernBERT layers. This tests whether adapting the top 8 layers improves over the released top-4-layer setup without changing supervision, decoder, or window parameters.

```bash
make layer-experiment-plan CFG=configs/experiments/layers-v2.0.0.mk
make layer-experiment-train CFG=configs/experiments/layers-v2.0.0.mk
make layer-experiment-evaluate CFG=configs/experiments/layers-v2.0.0.mk
make layer-experiment-report CFG=configs/experiments/layers-v2.0.0.mk
```

Fixed protocol:

- training supervision: `all_subtokens_b_to_i`
- decoder: `first_subtoken_viterbi`
- window: `512/256/32`
- seeds: `17`, `42`, `73`
- layer settings: `4`, `8`

The 4-layer cells reuse the `decoding-v2.0.0` all-subtoken B-to-I baseline metrics. The experiment trains only the 8-layer cells and reports paired seed deltas against the 4-layer baseline.

Validation results:

| Unfrozen top layers | Runs | Entity F1 mean | F1 stdev | Precision mean | Recall mean |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 3 | 0.934203 | 0.006402 | 0.952969 | 0.916208 |
| 8 | 3 | 0.933544 | 0.005805 | 0.952874 | 0.914985 |

Paired seed deltas:

| Seed | Baseline layers | Baseline F1 | `layers8_minus_layers4` |
| --- | ---: | ---: | ---: |
| 17 | 4 | 0.935970 | -0.004386 |
| 42 | 4 | 0.927103 | 0.001869 |
| 73 | 4 | 0.939535 | 0.000540 |
| mean | 4 |  | -0.000659 |

The 8-layer setting did not improve validation performance. The mean paired delta is effectively neutral and slightly favors the 4-layer setup, so the 4-layer adaptation remains the more efficient default for the v2 protocol.

For basic curation of the existing HIPE-derived French/German dev and test folds, run the configured v2 model over both splits and build disagreement records for manual review:

```bash
make suggest-eval-disagreements
```

To build only one fold's review queue, use `make suggest-eval-disagreements-validation` or `make suggest-eval-disagreements-test`. The checker is self-contained: `CURATION_MODEL` and `CURATION_LABEL_MAP` must belong to the same trained model. If the v2 model has not been trained yet, run `make train` first.

The review files are written below `data/curated/legacy-eval-curation/review/`, including split/language files such as `validation_de_disagreements.jsonl`, `validation_fr_disagreements.jsonl`, `test_de_disagreements.jsonl`, and `test_fr_disagreements.jsonl`. Each row contains a deterministic `review_id`, document metadata, gold entity, predicted entity, token context, and a `decision` block for manual curation.

For iterative or multi-reviewer curation, store decisions in `data/curated/legacy-eval-curation/review/decisions.jsonl` and regenerate the review files. Rows with a matching `review_id` are marked with the saved decision, and remaining items are written to `todo_disagreements.jsonl`.

To test a short terminal curation session:

```bash
make review-curation REVIEWER="$USER" ARGS="--limit 1"
make curation-review
make validate-curation ARGS=--no-require-complete
```

The reviewer appends to `decisions.jsonl`; it does not modify the generated disagreement files.

Before committing curation decisions, validate that every current disagreement has exactly one completed decision:

```bash
make curation-review
make validate-curation
```

Use `ARGS=--no-require-complete` only for in-progress review snapshots.

After validation, apply the reviewed decisions to a new curated JSONL directory:

```bash
make apply-curation
```

This writes revised HIPE-derived folds to `data/curated/legacy-import-curated/` and leaves the original `data/curated/legacy-import/` files untouched. The output includes `train.jsonl`, `validation.jsonl`, `test.jsonl`, `label_map.json`, `curation_changes.jsonl`, `curation_changes_tags.tsv`, and `curation_summary.json`. Manual corrections entered with `m` are stored as structured token spans and applied directly.

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
make push-model MODEL=models.d/newsagency_radiostation_modernbert_v2.0.0_continue1/best
```

See [docs/curation.md](docs/curation.md) for full curation workflows, path selection, and command assumptions.

## Task Cheat Sheet

| If you want to... | Call this target | `CFG=...`? |
| --- | --- | --- |
| See the main help and target groups. | `make` | Not needed. |
| Refresh annotation checks, coverage, profiles, and curation state. | `make anno-housekeeping` | Yes, to choose another dataset/model config. |
| Refresh dataset checks, TSV views, statistics, label map, and quality reports. | `make data-housekeeping` | Yes, to choose another dataset/model config. |
| Check current annotation, snippet, and dataset progress. | `make curation-state` | Yes, to inspect another configured prerelease/model. |
| Validate token offsets, BIO labels, entities, and minimal JSONL fields. | `make validate-jsonl-format` | Yes, if validating another configured dataset. |
| Validate one patched JSONL before copying it into a split. | `make validate-jsonl-format JSONL_FORMAT_JSONL=data/curated/tsv-segment-replacements/train/patched.jsonl` | Yes, if the patch belongs to another configured dataset. |
| Generate the BIO-complete dataset label map from train/validation/test plus seed metadata. | `make sync-label-map` | Yes, if the target dataset comes from another config. |
| Generate release dataset statistics. | `make dataset-statistics` | Yes, if the target dataset comes from another config. |
| Generate validation/test model quality and coverage reports. | `make dataset-quality-analysis` | Yes, to evaluate/report with another configured model. |
| Materialize TOKEN/NERTAG TSV files for inspection and manual patching. | `make materialize-dataset-tsv` | Yes, if the target dataset comes from another config. |
| Search the materialized TSV by token text. | `make search-tsv TSV_SEARCH="Radio London"` | Yes, if searching TSVs for another config. |
| Search the materialized TSV by entity tag. | `make search-tsv TSV_SEARCH_TAG="org.ent.pressagency.apa"` | Yes, if searching TSVs for another config. |
| Create TSV-derived span patches from pasted TOKEN OLD \[NEW\] lines across train/validation/test. | `make create-tsv-span-patches` | Yes, if patching another configured dataset. |
| Replace an exact TOKEN/NERTAG segment with a clean TOKEN/NERTAG block; in the replacement block, optional `_` after a row suppresses the default following space. | `make replace-tsv-segment TSV_SEGMENT_SPLIT=train TSV_SEGMENT_OLD=/tmp/old.tsv TSV_SEGMENT_NEW=/tmp/new.tsv` | Yes, if patching another configured dataset. |
| Apply and promote TSV-derived span patches, then refresh TSV and annotation reports. | `make create-tsv-span-patches integrate-tsv-span-patches materialize-dataset-tsv anno-housekeeping` | Yes, keep the same `CFG=...` across the whole chain. |
| Sample focused press-agency snippets for under-covered labels. | `make sample-media-snippets MEDIA_FAMILY=pressagency` | Yes, coverage and outputs follow the config. |
| Sample focused radio-station snippets for under-covered labels. | `make sample-media-snippets MEDIA_FAMILY=radiostation` | Yes, coverage and outputs follow the config. |
| Force sampling for one press-agency label. | `make sample-freely-media-snippets MEDIA_FAMILY=pressagency MEDIA_LABELS=org.ent.pressagency.cip MEDIA_SAMPLE_MAX_QUERIES_PER_LABEL=0` | Yes, outputs and existing-data filters follow the config. |
| Suggest model/metadata spans for sampled snippets. | `make suggest-media-snippet-spans MEDIA_FAMILY=pressagency` | Yes, to use the configured scorer model. |
| Review sampled snippet spans. | `make review-media-snippet-spans MEDIA_FAMILY=pressagency REVIEWER="$USER"` | Usually yes, to read/write the matching configured snippet files. |
| Put accepted/rejected reviewed snippets into train only. | `make split-media-snippets MEDIA_FAMILY=pressagency SNIPPET_VALIDATION_FRACTION=0.0 SNIPPET_TEST_FRACTION=0.0 HOLDOUT_MIN_PER_LABEL=0` | Yes, split outputs and holdout sources follow the config. |
| Promote split snippets into the configured dataset. | `make integrate-snippets` | Yes, because it changes the configured dataset splits. |
| Materialize the exact published HF dataset locally. | `make download-hf-dataset CFG=configs/model-v2.0.0-4layers-hf-verification.mk` | Yes, use the HF-verification config to pin the dataset commit. |
| Compare the local HF dataset materialization with the immutable Git release. | `make compare-hf-dataset-release CFG=configs/model-v2.0.0-4layers-hf-verification.mk` | Yes, use the same config used for HF materialization. |
| Evaluate the configured model into model-local diagnostics. | `make test EVAL_PREDICTION_DIAGNOSTICS=true` | Yes, to evaluate a model variant such as the 4-layer config. |
| Evaluate the official test split into model-local diagnostics. | `make test-official EVAL_PREDICTION_DIAGNOSTICS=true` | Yes, to evaluate a model variant such as the 4-layer config. |
| Evaluate train/validation/test into shared curation disagreement inputs. | `make curation-eval` | Yes, to choose the curation checker model/dataset. |
| Build and review gold-vs-prediction disagreements. | `make suggest-eval-disagreements` | Yes, to use the configured curation eval paths. |
| Audit illegal BIO transitions in prediction diagnostics. | `make audit-predicted-iob PREDICTED_IOB_SPLIT=validation` | Yes, if diagnostics were generated under another config. |
| Audit subtoken prediction consistency in diagnostics. | `make audit-subtokens SUBTOKEN_AUDIT_SPLIT=validation` | Yes, if diagnostics were generated under another config. |
| Train the default v2 model. | `make train` | Yes, use `CFG=...` to train a model variant. |
| Remove the configured model directory and train from scratch. | `make train-fresh` | Yes, use `CFG=...` to choose which model directory is cleaned and trained. |
| Train the v2 variant that adapts the final 4 ModernBERT layers. | `make train-fresh CFG=configs/model-v2.0.0-4layers.mk` | Already supplied. |
| Train a fresh 4-layer verification model from the pinned HF v2.0.0 dataset. | `make train-fresh CFG=configs/model-v2.0.0-4layers-hf-verification.mk` | Already supplied. |

## Common Commands

```bash
make help
make smoke
make clean-dry-run
make validate-labels
make sample-freely-newsagency-snippets ARGS="--dry-run --labels org.ent.pressagency.reuters --max-queries-per-label 1"
make sample-freely-radio-snippets ARGS="--dry-run --labels org.ent.radiostation.rtl --max-queries-per-label 1"
make export-dataset
make download-mlm-sources
make build-mlm-data
make pretrain-mlm
make push-mlm-model
make publish-dataset ARGS="--dry-run"
make publish-testset ARGS="--dry-run"
make train CFG=configs/model-v2.0.0.mk
make test CFG=configs/model-v2.0.0.mk
make apply-curation CFG=configs/model-v2.0.0.mk
make suggest-media-snippet-spans CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=pressagency
make review-media-snippet-spans CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=pressagency REVIEWER="$USER"
make split-media-snippets CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=pressagency
make suggest-media-snippet-spans CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=radiostation
make review-media-snippet-spans CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=radiostation REVIEWER="$USER"
make split-media-snippets CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=radiostation
make push-model CFG=configs/model-v2.0.0.mk
```

For Impresso API sampling, the token is entered interactively when the sampler connects and is reused through the `impresso-py` token cache.

You can create a local `.env` for non-secret Impresso API settings and optional Hugging Face authentication:

```bash
cp .env.example .env
```

By default `IMPRESSO_PERSISTED_TOKEN=true`, so the `impresso` client prompts for the Impresso API token once and can write it to `~/.impresso_py.yml`. Set it to `false` if you want interactive token entry without writing the cache file. Alternatively, set `IMPRESSO_API_TOKEN` in `.env` to use that token directly; in that mode the workbench does not call the `impresso-py` cache. `.env` is gitignored.

## Publish Dataset

The training dataset publisher prepares a Hugging Face-ready projection from the configured dataset source without uploading by default:

```bash
make publish-dataset
```

By default this reads the dataset source configured by `CFG` and writes `staging.d/datasets/impresso-mediaagencies-ner-dataset/` with:

```text
README.md
data/train.jsonl
data/validation.jsonl
data/test.jsonl
label_map.json
DATASET_STATISTICS.md
```

The publisher validates entity labels against `resources/newsagency_seeds.json` and `resources/radiostation_seeds.json`. To upload after inspecting the staged directory:

```bash
make publish-dataset ARGS="--upload"
```

The staged `data/*.jsonl` files are compact public training files, not byte-for-byte copies of the converted HIPE import. They keep the useful model/data fields (`text`, `tokens`, token offsets, BIO labels, entity spans, document metadata, quality flags) and group only minimal trace-back fields under `legacy`. In that field name, `legacy` means retained HIPE import trace-back metadata, not data that is obsolete. Large conversion/debug fields such as `segments`, `sentences`, `token_nel`, `token_ocr`, `token_render`, and `token_segment_ids` stay in the local curated source unless explicitly needed for an audit workflow.

To open a Hub pull request instead of pushing directly:

```bash
make publish-dataset ARGS="--upload --create-pr"
```

Most commands are scaffolded and will become active as the implementation lands.

## Cleaning Local State

Use `make clean-dry-run` to inspect local generated workbench data that can be removed. Use `make clean` to remove ignored generated roots and local working data, including `staging.d/`, `models.d/`, `mlm.d/`, `hf.d/`, `cache.d/`, `data/candidates/`, `data/curated/`, and `data/testset/`.

Committed prerelease and release snapshots under `data/prereleases/` and `data/releases/` are preserved. Promote curation into `data/prereleases/<dataset-version>/` before cleaning if it should become shared project state.

## State Summaries

Use these targets to check local curation progress and dataset staging state:

```bash
make curation-state CFG=configs/model-v2.0.0.mk
make snippet-state CFG=configs/model-v2.0.0.mk
make eval-disagreement-state CFG=configs/model-v2.0.0.mk
make dataset-state CFG=configs/model-v2.0.0.mk
make curation-state-json CFG=configs/model-v2.0.0.mk
```

`curation-state-json` writes `staging.d/reports/curation_state.json` by default. To check the Hugging Face dataset repository over the network, pass `ARGS="--fetch-published"` to `dataset-state` or `curation-state`.

## Language-Aware Coverage

Coverage and targeted sampling are label-language aware. By default, `de`, `fr`, and `en` are main languages with a target of 20 accepted examples per label and language; `lb` and `it` are side languages with a target of 5. The default sampler language lists follow these configured main and side languages.

```bash
make annotation-stats CFG=configs/model-v2.0.0.mk
make sample-media-snippets CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=pressagency
make sample-media-snippets CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=radiostation
```

Restrict a sampling pass to one canonical label with `ARGS="--labels ..."`:

```bash
make sample-media-snippets CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=pressagency ARGS="--labels org.ent.pressagency.reuters"
make sample-media-snippets CFG=configs/model-v2.0.0.mk MEDIA_FAMILY=radiostation ARGS="--labels org.ent.radiostation.rtl"
```

Override the defaults from the command line when needed:

```bash
make annotation-stats CFG=configs/model-v2.0.0.mk ANNOTATION_MAIN_LANGS="de fr en" ANNOTATION_SIDE_LANGS="lb it" ANNOTATION_MAIN_TARGET_PER_LABEL_LANG=20 ANNOTATION_SIDE_TARGET_PER_LABEL_LANG=5
make annotation-stats CFG=configs/model-v2.0.0.mk ANNOTATION_LANGUAGE_TARGETS="de=30 fr=30 en=20 lb=8 it=8"
```

## Plan

See [WORKBENCH_PLAN.md](WORKBENCH_PLAN.md) for the implementation plan and thesis-derived requirements.

See [docs/annotation_guidelines.md](docs/annotation_guidelines.md) for the news-agency and radio-station annotation rules.

See [docs/curation.md](docs/curation.md) for the HIPE-derived dev/test curation and review workflow.

See [docs/jsonl_schema.md](docs/jsonl_schema.md) for the annotated JSONL field contract and its mapping from the HIPE TSV CoNLL-style format.

See [docs/hipe_to_jsonl_conversion_plan.md](docs/hipe_to_jsonl_conversion_plan.md) for the concrete conversion workflow from the original HIPE data into the new JSONL dataset.

See [GENERATED_DIRS.md](GENERATED_DIRS.md) for the local generated-directory convention.

See [docs/data_lifecycle.md](docs/data_lifecycle.md) for local, committed, and published dataset state.

See [RELEASE_MANAGEMENT_PLAN.md](RELEASE_MANAGEMENT_PLAN.md) for prerelease, release, staging, and audit-storage policy.

See [RELEASE_PROCESS.md](RELEASE_PROCESS.md) for the step-by-step data release checklist.
