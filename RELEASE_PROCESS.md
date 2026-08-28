# Release Process

This is the operational release checklist for agents working in the workbench.

The policy is defined in `RELEASE_MANAGEMENT_PLAN.md`. This document tells you what to do.

## Prepare

## 1. Start A Release Branch

Create one branch per target dataset release:

```bash
git switch -c release/dataset-v2.0.0
```

Use this branch for collaborative prerelease work. Do not keep prerelease snapshots on `main` after publication.

## 2. Prepare Local Working Data

Use the normal ignored work areas while sampling, scoring, reviewing, and exporting:

```text
data/candidates/
data/curated/
data/testset/
release-work.d/
audit.d/
staging.d/
```

These paths are not shared source of truth. They may be removed by `make clean`.

Before creating a prerelease, make sure the relevant local curation/export commands have been run and checked:

```bash
make curation-state CFG=configs/model-v2.0.0.mk
make annotation-stats CFG=configs/model-v2.0.0.mk
make clean-dry-run
```

Classify each data change before it enters a prerelease:

- horizontal extension: more documents/examples for existing labels
- vertical extension: deeper annotation or new entity families inside existing documents
- repair: missed-span fixes or corrected existing annotations found by audit

Keep these counts separate in notes and manifests. See `DATASET_EXTENSION_PLAN.md`.

## 3. Update The Committed Prerelease Snapshot

Create or refresh exactly one prerelease folder for the target release:

```text
data/prereleases/dataset-v2.0.0/
```

Update this folder in place. Do not create `rc.1`, `rc.2`, or date-stamped prerelease folders for the same target release. In-place updates make the candidate reviewable with normal git diffs.

The prerelease folder must use the compact public training schema, but it is a flat source snapshot. `make publish-dataset` later converts it into the Hugging Face payload shape under `staging.d/datasets/...`.

```text
data/prereleases/dataset-v2.0.0/
  train.jsonl
  validation.jsonl
  test.jsonl
  label_map.json
  dataset_summary.json
  manifest.json
  DATASET_STATISTICS.md
  DATASET_QUALITY.md
  tsv/
    train.tsv
    validation.tsv
    test.tsv
```

Rows must use the public dataset projection, not the local import schema. Do not include local-only fields such as:

```text
segments
sentences
token_render
token_nel
token_ocr
token_segment_ids
```

Keep bulky provenance in `audit.d/` or S3, not in git.

`DATASET_QUALITY.md` and `tsv/` are prerelease review aids. They are not part of the Hugging Face dataset payload or the immutable Git final release projection.

## 4. Validate The Prerelease

Before committing prerelease updates, check:

- every file listed in `manifest.json` exists
- JSON and JSONL files parse cleanly
- labels are present in canonical metadata
- split counts and language counts are plausible
- `label_map.json` is BIO-complete and includes canonical seed metadata labels
- JSONL rows are sorted by `document_id`/`id`
- JSON object keys are written alphabetically
- no file is above 100 MiB
- no normal git file is above 50 MiB unless explicitly accepted
- `audit.d/`, `release-work.d/`, and `staging.d/` are ignored

Run the available project checks:

```bash
make smoke
make data-housekeeping CFG=configs/model-v2.0.0.mk
make anno-housekeeping CFG=configs/model-v2.0.0.mk
make prepare-dataset-release CFG=configs/model-v2.0.0.mk
```

`make prepare-dataset-release` refreshes the configured prerelease's
`label_map.json`, `DATASET_STATISTICS.md`, TSV views, `dataset_summary.json`,
and `manifest.json`, validates the split files, and removes accidental
`.DS_Store` files from the prerelease tree. It leaves the manifest in
`prerelease` status by default. Use `DATASET_RELEASE_STATUS=ready` only after
the exact candidate has been reviewed and accepted for publication.

Inspect git state:

```bash
git status --short
git status --ignored --short data/prereleases data/releases audit.d release-work.d staging.d
```

## Review And Freeze

## 5. Commit Prerelease Work For Review

Commit the prerelease candidate on the release branch:

```bash
git add data/prereleases/dataset-v2.0.0
git commit -m "Prepare dataset-v2.0.0 prerelease"
```

Collaborators should review the release branch diff. If curation changes, regenerate the prerelease snapshot in the same folder and commit another update on the same branch.

When the exact candidate is accepted, freeze it explicitly:

```bash
make prepare-dataset-release CFG=configs/model-v2.0.0.mk DATASET_RELEASE_STATUS=ready
git add data/prereleases/dataset-v2.0.0
git commit -m "Freeze dataset-v2.0.0 prerelease"
```

This `ready` commit is the source snapshot for staging, publication, audit archival, and final release promotion. "Frozen" means that this committed Git snapshot is accepted for publication. It does not mean that the files are filesystem read-only.

After this point, do not run annotation, sampling, snippet integration, TSV repair, or other source-content-changing targets against this release candidate. If a content issue is found, return the candidate to normal prerelease work, fix it, rerun `make prepare-dataset-release` with the default `prerelease` status, review the diff, and create a new `ready` commit.

## Publish

## 6. Optionally Prepare Audit Material

If the release has coherent audit/provenance material worth archiving externally, prepare the full audit hierarchy for S3 or another approved external store. External audit archival is optional and is not a prerequisite for dataset or model publication.

Use this shape:

```text
s3://<audit-bucket>/impresso-mediaagencies-workbench/prereleases/dataset-v2.0.0/
  hf/
  sources/
  audit/
  checks/
```

The `hf/` folder should contain the exact staged Hugging Face payload. The `audit/` and `sources/` folders may contain full local conversion, sampling, review, and curation provenance.

Large provenance material can be uploaded before publication, but the archive is not final until the published Hugging Face revision metadata has been added.

## 7. Publish The Dataset

Before publishing, verify that the ready candidate has not changed locally:

```bash
git status --short data/prereleases/dataset-v2.0.0
```

The intended publishing invariant is:

- `manifest.json` has `status: ready`
- the dataset source path is clean relative to Git
- staging and upload derive from the committed ready snapshot

Stage and inspect the accepted prerelease payload:

```bash
make publish-dataset CFG=configs/model-v2.0.0.mk ARGS="--dry-run"
```

The dry run is intentionally dependency-light. It should work even when the active Python environment does not have `huggingface_hub` installed, because it does not upload.

Create the local staged Hugging Face payload for inspection:

```bash
make publish-dataset CFG=configs/model-v2.0.0.mk
```

Inspect `staging.d/datasets/impresso-mediaagencies-ner-dataset/`. This directory is generated and ignored; do not commit it.

Then publish or open a Hugging Face PR according to the release decision:

```bash
make publish-dataset CFG=configs/model-v2.0.0.mk ARGS="--upload --create-pr"
```

After publication, record the Hugging Face commit SHA and final status in `manifest.json`:

```bash
make finalize-dataset-release CFG=configs/model-v2.0.0.mk HF_COMMIT_SHA=<40-character-hf-commit-sha>
git add data/prereleases/dataset-v2.0.0/manifest.json
git commit -m "Record dataset-v2.0.0 publication metadata"
```

This changes the manifest from `ready` to `published`. Running the same command again with the same publication metadata is allowed; using a different Hugging Face commit SHA for an already published manifest must fail.

## Finalize

## 8. Optionally Finalize Audit Archive

If an external audit archive exists, finalize it with the published Hugging Face revision metadata and record the archive prefix in `manifest.json`.

## 9. Promote To Final Release

Project the published prerelease to the final release folder:

```text
data/releases/dataset-v2.0.0/
```

```bash
make promote-dataset-release CFG=configs/model-v2.0.0.mk
```

The final release folder should contain the Git final release projection: `train.jsonl`, `validation.jsonl`, `test.jsonl`, `label_map.json`, `DATASET_STATISTICS.md`, `dataset_summary.json`, and `manifest.json`.

Final release IDs are immutable. Standard release tooling must refuse promotion if `data/releases/dataset-v2.0.0/` already exists. If the published content is wrong, create a patch release such as `dataset-v2.0.1`; do not overwrite `dataset-v2.0.0`.

The final `manifest.json` should include:

- `status: published`
- Hugging Face dataset repo
- Hugging Face commit SHA
- S3 audit prefix, if available
- source prerelease path

The generated Hugging Face-shaped payload remains under `staging.d/datasets/...` and is not committed.

Remove the prerelease folder before merging to `main`:

```bash
git rm -r data/prereleases/dataset-v2.0.0
git add data/releases/dataset-v2.0.0
git commit -m "Publish dataset-v2.0.0 release snapshot"
```

## Finish

## 10. Merge Back To Main

Only final release material should land on `main`:

```text
data/releases/dataset-v2.0.0/
```

`main` should not retain:

```text
data/prereleases/dataset-v2.0.0/
release-work.d/
audit.d/
staging.d/
```

The release branch and PR history remain the collaboration record for prerelease changes.

## 11. Clean Local Workbench State

After the final release is committed and any intended audit material has been archived externally:

```bash
make clean-dry-run
make clean
```

`make clean` removes ignored local work and preserves committed `data/prereleases/` and `data/releases/` paths. On `main`, `data/prereleases/` should normally contain only `.gitkeep`.

## Verify Published Dataset

## 12. Verify The Hugging Face Projection

After the dataset release has reached `main`, verify that the published Hugging Face dataset commit materializes to the expected public projection of the Git final release.

Use a verification config pinned to the published Hugging Face dataset commit:

```bash
make CFG=configs/model-v2.0.0-4layers-hf-verification.mk download-hf-dataset
make CFG=configs/model-v2.0.0-4layers-hf-verification.mk compare-hf-dataset-release
```

The JSONL comparison is projection-aware. The Git final release can retain provenance fields deliberately excluded from the public Hugging Face representation, such as top-level `legacy` fields and entity-level review/provenance fields. `label_map.json` should compare exactly.

## Model Release

## 13. Start A Model Release Branch

Create a separate branch for the model release. Do not modify the immutable dataset release:

```bash
git switch main
git pull --ff-only origin main
git switch -c release/model-v2.0.0
```

## 14. Train From The Published Dataset

Model release training must use the pinned published Hugging Face dataset, not the mutable prerelease folder and not an accidental local candidate file.

Ensure the exact pinned dataset commit has passed step 12. If the local Hugging Face materialization is absent or its provenance is uncertain, materialize and verify it again:

```bash
make CFG=configs/model-v2.0.0-4layers-hf-verification.mk download-hf-dataset
make CFG=configs/model-v2.0.0-4layers-hf-verification.mk compare-hf-dataset-release
```

Then run inexpensive validation before training:

```bash
make CFG=configs/model-v2.0.0-4layers-hf-verification.mk validate-jsonl-format
```

Train into a fresh model directory configured for this model candidate:

```bash
make CFG=configs/model-v2.0.0-4layers-hf-verification.mk train
```

The model config should record the released dataset revision, the pinned Hugging Face dataset commit, the base model, label-supervision strategy, decoder strategy, and adaptation setting such as the number of unfrozen layers.

## 15. Evaluate And Select The Model

Evaluate validation and test with the release decoder:

```bash
make CFG=configs/model-v2.0.0-4layers-hf-verification.mk evaluate-validation
make CFG=configs/model-v2.0.0-4layers-hf-verification.mk evaluate-test
```

Record validation metrics, held-out test metrics, the selected checkpoint path, and any diagnostic outputs used to select the model. The decoder must use the checkpoint's configured BIO label vocabulary; the dataset label map must not silently resize or reinitialize the classifier head.

## 16. Publish The Model

Prepare the model card and publication payload from the selected checkpoint. Record at least:

- Hugging Face dataset repository and exact dataset commit SHA
- workbench/training-code Git commit SHA
- base model identifier and revision
- training config
- random seed
- label map
- tokenization and supervision strategy
- unfrozen layer count or equivalent adaptation strategy
- decoder and evaluation strategy
- selected checkpoint
- validation and test metrics
- Hugging Face model repository and model commit SHA after publication

For v2.0.0, the completed training run did not record a training-code Git SHA in `training_start_report.json`. Record that value as unknown rather than substituting the later publication/workbench commit. Future training runs should record the workbench Git commit and dirty/clean status automatically in `training_start_report.json`.

Publish the selected checkpoint using the configured model publication workflow. The publication command must upload the selected checkpoint, model card, label configuration, decoding metadata, and training provenance. If no model publication target exists yet, finalize that target before treating this checklist step as complete.

After model publication, validate runtime inference against the evaluator's decoded predictions. For a local release-artifact verification, point the parity check at the downloaded model artifact, release test split, and evaluator output:

```bash
make compare-model-inference-parity \
  MODEL_INFERENCE_PARITY_MODEL=hf.d/model-v2.0.0 \
  MODEL_INFERENCE_PARITY_INPUT_JSONL=data/releases/dataset-v2.0.0/test.jsonl \
  MODEL_INFERENCE_PARITY_EVALUATOR_PREDICTIONS=staging.d/v2.0.0-test-eval/test_predictions.jsonl \
  MODEL_INFERENCE_PARITY_SUMMARY_JSON=staging.d/v2.0.0-test-inference-parity-summary.json \
  MODEL_INFERENCE_PARITY_MISMATCHES_JSONL=staging.d/v2.0.0-test-inference-parity-mismatches.jsonl
```

The acceptance criterion is exact parity: all held-out test documents must have identical decoded token-label sequences between evaluator and runtime pipeline, and recomputed entity/token metrics must match. For v2.0.0 this check matched 458 / 458 held-out test documents and reproduced 529 / 612 / 566 exact entities with F1 0.8981324278.

If the Hugging Face model repository still contains an older placeholder `pipeline.py`, publish a runtime-only model update before treating remote consumer inference as complete. This update must not retrain the model or change dataset provenance; it only replaces the runtime files and model card/provenance needed for inference.

After model publication and inference validation, commit the model-release metadata and merge the model release branch through the normal PR/review path.

## 17. Attach Post-Release Model Experiments

After the model release is stable, validation-only experiments can be attached as release evidence for future model choices. These experiments must not modify the immutable dataset release or use the held-out test set for model selection.

For decoder/supervision robustness:

```bash
make decoding-experiment-plan CFG=configs/experiments/decoding-v2.0.0.mk
make decoding-experiment-train CFG=configs/experiments/decoding-v2.0.0.mk
make decoding-experiment-evaluate CFG=configs/experiments/decoding-v2.0.0.mk
make decoding-experiment-report CFG=configs/experiments/decoding-v2.0.0.mk
```

The decoder report should include raw argmax and Viterbi variants for both first-subtoken and all-subtoken emissions. Document what the all-subtoken decoder consumes: aggregated emissions from all model subtokens belonging to each annotation token. Record paired deltas against the deployed decoder to document the expected cost of changing runtime decoding, and note when a decoder is only appropriate with matching training supervision.

For context-window robustness:

```bash
make context-experiment-evaluate CFG=configs/experiments/context-inference-v2.0.0.mk
make context-experiment-report CFG=configs/experiments/context-inference-v2.0.0.mk
```

Record the resulting summaries in the workbench README and, when they justify release defaults, in the model card. Keep the model card concise: include conclusions and key validation numbers, not every intermediate artifact. These reports are post-release validation evidence unless they are run before selecting a new model release candidate.

## 18. Close The Model Release

After the model release branch has been reviewed and merged:

1. Verify that `main` contains the model-release commits.
2. Delete the local and remote model-release branch.
3. Verify that the working tree is clean.
4. Run `make clean-dry-run`.
5. When the generated/local state is no longer needed, run `make clean`.

Cleanup removes ignored workbench state such as downloaded Hugging Face materializations, trained model directories, reports, caches, staging directories, and local curation state. It does not remove committed immutable dataset releases.

After cleanup, `main` with a clean working tree is the baseline for the next development or release cycle.
