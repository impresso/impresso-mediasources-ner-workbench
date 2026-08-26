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

## 6. Prepare Audit Material

Before publication, prepare the full audit hierarchy for S3 or another approved external store.

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

After publication, record the Hugging Face commit SHA and final status in `manifest.json`.

## Finalize

## 8. Finalize Audit Archive

Finalize the audit archive with the published Hugging Face revision metadata and record the S3 prefix in `manifest.json`, if available.

## 9. Promote To Final Release

Project the accepted prerelease to the final release folder:

```text
data/releases/dataset-v2.0.0/
```

```bash
make promote-dataset-release CFG=configs/model-v2.0.0.mk
```

The final release folder should contain the Git final release projection: `train.jsonl`, `validation.jsonl`, `test.jsonl`, `label_map.json`, `DATASET_STATISTICS.md`, `dataset_summary.json`, and `manifest.json`. Publication metadata in `manifest.json` may be finalized during promotion.

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

After the final release is committed and audit material is archived externally:

```bash
make clean-dry-run
make clean
```

`make clean` removes ignored local work and preserves committed `data/prereleases/` and `data/releases/` paths. On `main`, `data/prereleases/` should normally contain only `.gitkeep`.
