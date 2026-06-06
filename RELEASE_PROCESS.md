# Release Process

This is the operational release checklist for agents working in the workbench.

The policy is defined in `RELEASE_MANAGEMENT_PLAN.md`. This document tells you what to do.

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

The prerelease folder must be Hugging Face-shaped:

```text
data/prereleases/dataset-v2.0.0/
  README.md
  data/
    train.jsonl
    validation.jsonl
    test.jsonl
  label_map.json
  dataset_summary.json
  manifest.json
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

## 4. Validate The Prerelease

Before committing prerelease updates, check:

- every file listed in `manifest.json` exists
- JSON and JSONL files parse cleanly
- labels are present in canonical metadata
- split counts and language counts are plausible
- JSONL rows are sorted by `document_id`/`id`
- JSON object keys are written alphabetically
- no file is above 100 MiB
- no normal git file is above 50 MiB unless explicitly accepted
- `audit.d/`, `release-work.d/`, and `staging.d/` are ignored

Run the available project checks:

```bash
make smoke
make validate-labels
make curation-state CFG=configs/model-v2.0.0.mk
```

Inspect git state:

```bash
git status --short
git status --ignored --short data/prereleases data/releases audit.d release-work.d staging.d
```

## 5. Commit Prerelease Work For Review

Commit the prerelease candidate on the release branch:

```bash
git add data/prereleases/dataset-v2.0.0
git commit -m "Prepare dataset-v2.0.0 prerelease"
```

Collaborators should review the release branch diff. If curation changes, regenerate the prerelease snapshot in the same folder and commit another update on the same branch.

## 6. Archive Full Audit Material

Before publication, copy the full audit hierarchy to S3 or another approved external store.

Use this shape:

```text
s3://<audit-bucket>/impresso-mediaagencies-workbench/prereleases/dataset-v2.0.0/
  hf/
  sources/
  audit/
  checks/
```

The `hf/` folder should contain the exact prerelease payload. The `audit/` and `sources/` folders may contain full local conversion, sampling, review, and curation provenance.

Record the S3 prefix in `manifest.json`.

## 7. Publish The Dataset

Stage and inspect the accepted prerelease payload:

```bash
make publish-dataset CFG=configs/model-v2.0.0.mk DATASET_SOURCE_DIR=data/prereleases/dataset-v2.0.0 ARGS="--dry-run"
```

Then publish or open a Hugging Face PR according to the release decision:

```bash
make publish-dataset CFG=configs/model-v2.0.0.mk DATASET_SOURCE_DIR=data/prereleases/dataset-v2.0.0 ARGS="--upload --create-pr"
```

After publication, record the Hugging Face commit SHA and final status in `manifest.json`.

## 8. Promote To Final Release

Copy the accepted prerelease to the final release folder:

```text
data/releases/dataset-v2.0.0/
```

The final release folder must contain the same HF-shaped payload that was published, plus the final `manifest.json` with:

- `status: published`
- Hugging Face dataset repo
- Hugging Face commit SHA
- S3 audit prefix, if available
- source prerelease path

Remove the prerelease folder before merging to `main`:

```bash
git rm -r data/prereleases/dataset-v2.0.0
git add data/releases/dataset-v2.0.0
git commit -m "Publish dataset-v2.0.0 release snapshot"
```

## 9. Merge Back To Main

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

## 10. Clean Local Workbench State

After the final release is committed and audit material is archived externally:

```bash
make clean-dry-run
make clean
```

`make clean` removes ignored local work and preserves committed `data/prereleases/` and `data/releases/` paths. On `main`, `data/prereleases/` should normally contain only `.gitkeep`.
