# Data Lifecycle

The workbench has three data layers:

- Local working data: ignored files used while sampling, scoring, reviewing, training, or staging.
- Committed prerelease snapshots: shared mutable release candidates under `data/prereleases/<dataset-version>/`.
- Committed release snapshots: immutable published dataset material under `data/releases/<dataset-version>/`.
- Published releases: Hugging Face dataset revisions built from committed release snapshots.

See `RELEASE_MANAGEMENT_PLAN.md` for the full prerelease, release, staging, and audit-storage policy. Follow `RELEASE_PROCESS.md` for the operational checklist.

## Dataset Extension Axes

Dataset updates must distinguish two axes:

- **Horizontal extension**: add more documents/examples for the current label space.
- **Vertical extension**: add more annotation depth or new entity families inside existing documents.

For example, adding more French `org.ent.pressagency.havas` examples is horizontal extension. Adding newspaper mentions such as `org.ent.newspaper.nzz` to already selected documents is vertical extension.

The span-patch review workflow supports vertical extension and missed-annotation repair:

```text
audit candidates -> review span patches -> append decisions -> apply patches -> refresh prerelease
```

See `DATASET_EXTENSION_PLAN.md` for the operational model.

## Local Working Data

The following paths are local work areas and are ignored by git:

- `data/candidates/`: sampled search results and sampling registries
- `data/curated/`: imported HIPE-derived data, review queues, decisions, scored snippets, reviewed snippets, and exported working JSONL
- `data/testset/`: local held-out testset work files
- `*.d/`: generated roots such as `staging.d/`, `models.d/`, `mlm.d/`, `hf.d/`, and `cache.d/`

These files are useful for day-to-day work, but they are not shared source of truth. A clean workbench may remove them.

## Committed Release Snapshots

When curation is ready for shared review but not final publication, commit one mutable prerelease snapshot under:

```text
data/prereleases/<dataset-version>/
```

Update that prerelease in place as the candidate changes, so collaborators can review normal git diffs.

When the dataset is published, promote the accepted prerelease to an immutable release snapshot under:

```text
data/releases/<dataset-version>/
```

A release snapshot should include the publishable split files and the audit material needed to understand the release:

```text
train.jsonl
validation.jsonl
test.jsonl
label_map.json
dataset_summary.json
curation_changes.jsonl
curation_changes_tags.tsv
curation_summary.json
```

Use the files that are relevant for the release. The important rule is that the committed release folder is enough to reconstruct or audit the Hugging Face dataset revision without relying on ignored local working files.

Large full-trace audit files should not be committed as normal git blobs. Keep them in an ignored `audit.d/` directory or external S3 audit storage, and reference them from `manifest.json` as audit evidence when they are useful for temporary inspection.

## Staging And Publishing

`staging.d/` is generated and ignored. It is the local inspection area for Hugging Face-ready files, not a source-of-truth directory.

The dataset release procedure should:

1. Read a committed snapshot from `data/releases/<dataset-version>/`.
2. Prepare the Hugging Face-ready repository files in `staging.d/datasets/...`.
3. Upload or open a Hugging Face pull request.
4. Record the published Hugging Face revision in the release config.

## Cleaning

Use:

```bash
make clean-dry-run
make clean
```

`make clean` removes ignored generated roots and local working data. It preserves committed prerelease and release snapshots under `data/prereleases/` and `data/releases/`.
