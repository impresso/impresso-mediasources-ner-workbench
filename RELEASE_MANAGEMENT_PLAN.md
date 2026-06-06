# Release Management Plan

This workbench separates private local work, committed collaborative prereleases, committed Hugging Face-shaped releases, generated staging, and full audit storage. Follow `RELEASE_PROCESS.md` for the operational checklist.

## Summary

- A **prerelease** is a committed, mutable release-candidate snapshot while multiple people are still accumulating and evaluating training data for one target release.
- A **real release** is an immutable, committed snapshot that reflects the Hugging Face dataset payload.
- Git stores compact, public-projection prereleases and releases.
- S3 stores the full release hierarchy, including bulky audit/provenance files.
- Dataset extension has two axes: **horizontal extension** adds more documents/examples; **vertical extension** adds more entity types or deeper annotations inside existing documents. Release notes and manifests should report these separately.

## Dataset Version Policy

Dataset versions use semantic major versions for entity-family scope:

- `v1.x.x`: press-agency-only baseline. `v1.0.0` is the first published Hugging Face baseline.
- `v2.x.x`: press agencies plus radio stations. `v2.0.0` is the active prerelease line.
- `v3.x.x`: first line that adds newspaper mentions as a new entity family.

Patch and minor versions stay within the same entity-family scope. For example, corrected HIPE-derived agency annotations and additional radio-station examples remain `v2.x.x` as long as no new entity family is added.

## Directory Layout

```text
data/
  prereleases/
    dataset-v2.0.0/
      README.md
      data/
        train.jsonl
        validation.jsonl
        test.jsonl
      label_map.json
      dataset_summary.json
      manifest.json

  releases/
    dataset-v1.0.0/
      README.md
      data/
        train.jsonl
        validation.jsonl
        test.jsonl
      label_map.json
      dataset_summary.json
      manifest.json

release-work.d/
  dataset-v2.0.0/
    sources/
      hipe-derived/
      snippets/
    merged/
    checks/
    manifest.json

staging.d/
  datasets/
    impresso-mediaagencies-ner-dataset/

audit.d/
  prereleases/
    dataset-v2.0.0/
  releases/
    dataset-v1.0.0/
```

External audit storage mirrors the full local audit hierarchy:

```text
s3://<audit-bucket>/impresso-mediaagencies-workbench/<release-kind>/<release-id>/
  hf/
    README.md
    data/train.jsonl
    data/validation.jsonl
    data/test.jsonl
    label_map.json
    dataset_summary.json
    manifest.json
  sources/
    hipe-derived/
    snippets/
  audit/
    conversion/
    curation/
    sampling/
  checks/
    checksums.json
    validation_report.json
```

`release-work.d/`, `staging.d/`, and `audit.d/` are ignored local roots. `data/prereleases/` and `data/releases/` are committed.

## Release States

- `working`: normal private sampling, scoring, review, and curation under ignored work areas.
- `prerelease`: one committed, mutable candidate exists under `data/prereleases/<release-id>/`.
- `ready`: the committed prerelease passed validation and size checks; no more data changes before publication.
- `published`: Hugging Face dataset revision exists and is recorded in the release manifest/config.
- `archived`: full source/audit hierarchy has been copied to S3; local `release-work.d/<release-id>/` and `audit.d/prereleases/<release-id>/` can be removed.

There is only one prerelease folder per target release. Update it in place so collaborators can review normal git diffs. Do not create `rc.1`, `rc.2`, etc. directories unless the target release version itself changes.

After publication and S3 audit upload, promote the accepted prerelease to `data/releases/<release-id>/`. Then remove `data/prereleases/<release-id>/` in a cleanup commit so the final published snapshot remains the durable in-repo release record.

## Git Prerelease And Release Snapshots

Committed prereleases and releases must reflect the Hugging Face dataset payload, not the local import schema. A prerelease may have `status: prerelease` in its manifest; a final release has `status: published`.

Required files:

```text
README.md
data/train.jsonl
data/validation.jsonl
data/test.jsonl
label_map.json
dataset_summary.json
manifest.json
```

Rows must use the public projection used by `lib.publish_dataset`: keep training fields and compact legacy trace fields; exclude local-only fields such as `segments`, `sentences`, `token_render`, `token_nel`, `token_ocr`, and `token_segment_ids`.

JSONL rows must be sorted by `document_id` or `id`, and JSON object keys must be written alphabetically. This keeps release diffs reviewable when prerelease snapshots are updated in place.

Git prerelease and release snapshots should avoid files above 50 MiB. Files above 100 MiB must not be committed because GitHub rejects them.

## S3 Audit Snapshot

The S3 audit location stores the full prerelease or release hierarchy for temporary or long-term provenance checks.

It should include:

- the exact HF payload
- source working inputs used to create the release
- full conversion and curation audit files
- sampling summaries and decision files
- checksums for every release file
- validation reports and published Hugging Face revision metadata

The committed `manifest.json` should reference the S3 audit prefix when available, but the prerelease or release must remain understandable without downloading the full audit hierarchy.

## Prerelease Workflow

1. Continue sampling/review/export in ignored local work areas.
2. Assemble or refresh private intermediate files under `release-work.d/<release-id>/` if useful.
3. Merge accepted sources into one public dataset snapshot.
4. Validate labels, splits, JSONL syntax, row counts, language coverage, and file sizes.
5. Classify the update as horizontal extension, vertical extension, or repair, and record separate counts for each category.
6. Write the HF-shaped candidate to `data/prereleases/<release-id>/`.
7. Commit updates to `data/prereleases/<release-id>/` so collaborators can review the diff.
8. Repeat steps 1-7 until the candidate is accepted.
9. Stage the accepted HF payload under `staging.d/datasets/...`.
10. Upload the full hierarchy to S3 audit storage.
11. Publish or open a Hugging Face PR.
12. Copy the accepted prerelease to `data/releases/<release-id>/`.
13. Record the Hugging Face commit SHA in `manifest.json` and release config.
14. Remove `data/prereleases/<release-id>/` and ignored local release work after publication and audit archival.

## Implementation Tasks

- Add a `prepare-prerelease` command that creates or updates HF-shaped `data/prereleases/<release-id>/` snapshots in place.
- Add a `promote-release` command that copies an accepted prerelease to immutable `data/releases/<release-id>/`.
- Add validation that fails on missing manifest files, JSONL parse errors, unknown labels, split leakage, and files larger than the configured threshold.
- Add optional S3 audit upload support with a configurable `RELEASE_AUDIT_S3_PREFIX`.
- Update `publish-dataset` to accept a committed prerelease or release snapshot as input and record the published Hugging Face revision in the manifest/config.
