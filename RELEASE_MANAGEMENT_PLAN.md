# Release Management Plan

This workbench separates private local work, committed collaborative prereleases, committed release snapshots, generated Hugging Face staging payloads, and full audit storage. Follow `RELEASE_PROCESS.md` for the operational checklist.

## Summary

- A **prerelease** is a committed, mutable release-candidate snapshot while multiple people are still accumulating and evaluating training data for one target release.
- A **ready** prerelease is an explicitly frozen, accepted Git snapshot intended for publication. Frozen means workflow-frozen by Git identity, not filesystem read-only.
- A **real release** is an immutable, committed snapshot that records the data used to create the Hugging Face dataset payload.
- Git stores compact, public-projection prereleases and releases.
- `staging.d/datasets/...` stores the generated Hugging Face payload shape used for upload.
- S3 stores the full release hierarchy, including bulky audit/provenance files.
- Dataset extension has two axes: **horizontal extension** adds more documents/examples; **vertical extension** adds more entity types or deeper annotations inside existing documents. Release notes and manifests should report these separately.

## Release Lifecycle

```text
working
  |
  v
prerelease --> review/fix --.
  ^                      |
  '----------------------'
  |
  v accepted
ready (frozen Git snapshot)
  |
  v
publish to Hugging Face
  |
  v
published
  |
  v
archive + promote
  |
  v
final release
```

The key boundary is `ready`: before it, dataset content may change; after it, publication must derive from the accepted committed snapshot.

Operational commands and the complete checklist live in `RELEASE_PROCESS.md`.

## Release Projections

The accepted prerelease is the complete Git source snapshot for a release operation. Hugging Face publication, final Git promotion, and audit archival derive purpose-specific projections from that snapshot.

| Artifact | HF dataset | Git final release | Workbench/audit |
| --- | --- | --- | --- |
| `train.jsonl` | yes | yes | yes |
| `validation.jsonl` | yes | yes | yes |
| `test.jsonl` | yes | yes | yes |
| `label_map.json` | yes | yes | yes |
| `DATASET_STATISTICS.md` | yes | yes | yes |
| `dataset_summary.json` | no | yes | yes |
| `manifest.json` | no | yes | yes |
| `DATASET_QUALITY.md` | no | no | yes |
| curation operation files | no | no | yes |
| `tsv/` materializations | no | no | yes |
| extensions and migration material | no | no | yes |

`DATASET_STATISTICS.md` is dataset-facing release documentation. `DATASET_QUALITY.md` is model/checkpoint-facing diagnostics and stays in the workbench or audit archive.

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

## Lifecycle Dimensions

Dataset lifecycle:

- `working`: normal private sampling, scoring, review, and curation under ignored work areas.
- `prerelease`: one committed, mutable candidate exists under `data/prereleases/<release-id>/`.
- `ready`: the committed prerelease passed validation and review; this exact Git snapshot is accepted for publication and no more data changes are expected before publication.
- `published`: Hugging Face dataset revision exists and is recorded in the release manifest/config.

Audit lifecycle:

- `local`: full source, curation, sampling, and check provenance exists under ignored local work areas.
- `archived`: full source/audit hierarchy has been copied to S3 or another approved external store.

Repository location:

- `data/prereleases/<release-id>/`: the collaborative release candidate.
- `data/releases/<release-id>/`: the immutable final in-repo release snapshot.

There is only one prerelease folder per target release. Update it in place so collaborators can review normal git diffs. Do not create `rc.1`, `rc.2`, etc. directories unless the target release version itself changes.

After publication and S3 audit upload, promote the accepted prerelease to `data/releases/<release-id>/`. Then remove `data/prereleases/<release-id>/` in a cleanup commit so the final published snapshot remains the durable in-repo release record.

## Technical Freeze Semantics

The freeze boundary is Git-native. It is not implemented with `chmod`, read-only filesystem flags, or other local working-copy permissions. Git does not preserve ordinary writable/read-only permissions in a useful cross-clone way, and local permission changes would make legitimate release metadata updates harder.

Running `make prepare-dataset-release DATASET_RELEASE_STATUS=ready` means:

- the current prerelease candidate has been reviewed and accepted for publication
- the manifest records `status: ready`
- the ready prerelease must be committed
- publication artifacts should be derived from that committed snapshot
- annotation, sampling, curation, snippet integration, TSV repair, or other source-content changes must stop for that candidate

Publication metadata may still be added later, because the Hugging Face revision and final audit prefix do not exist until after publication. If a content problem is discovered after the ready commit, the candidate should be treated as unfrozen: fix the data, regenerate metadata with `status: prerelease`, review again, then create a new `ready` commit.

The intended publish-time guard is:

- refuse to publish unless `manifest.json` has `status: ready`
- refuse to publish if `data/prereleases/<release-id>/` differs from the committed Git state
- preferably require a clean working tree, or at minimum a clean dataset source path

Final release immutability should be enforced by tooling, not filesystem permissions: a promotion command must fail if `data/releases/<release-id>/` already exists. Release IDs are immutable. If a published dataset needs a content correction, create a new patch release such as `dataset-v2.0.1` instead of overwriting `dataset-v2.0.0`.

## Git Prerelease And Release Snapshots

Committed prereleases and releases must use the compact public projection, not the local import schema. In the current implemented v2 workflow, committed prerelease snapshots are flat source snapshots. `make publish-dataset` converts that flat source into the Hugging Face payload shape under `staging.d/datasets/...`.

A prerelease should normally have `status: prerelease` while it is still being edited or reviewed. After collaborators accept an exact candidate, rerun `make prepare-dataset-release DATASET_RELEASE_STATUS=ready` to mark the freeze boundary. A final release has `status: published`.

Required files:

```text
train.jsonl
validation.jsonl
test.jsonl
label_map.json
dataset_summary.json
manifest.json
DATASET_STATISTICS.md
```

Recommended prerelease inspection files include `DATASET_QUALITY.md`, `tsv/train.tsv`, `tsv/validation.tsv`, and `tsv/test.tsv`. These files are useful during review but are not part of the HF dataset or immutable Git final release projections.

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

## Release Workflow

1. Build and iteratively review a prerelease.
2. Freeze the accepted candidate as `ready`.
3. Generate and publish the Hugging Face payload from that snapshot.
4. Finalize the external audit archive.
5. Promote the snapshot to an immutable final release.
6. Merge the final release to `main` and clean local work.

See `RELEASE_PROCESS.md` for commands and the complete operational checklist.

## Implementation Tasks

- `make prepare-dataset-release` is implemented. It refreshes release metadata for the configured flat prerelease snapshot, validates the split files, materializes TSV inspection files, and keeps the manifest in `prerelease` status by default. Pass `DATASET_RELEASE_STATUS=ready` only when freezing an accepted candidate.
- Add a `promote-release` command that copies an accepted prerelease to immutable `data/releases/<release-id>/`.
- Add explicit freeze metadata, such as the accepted prerelease Git commit SHA, before publication.
- Extend validation so release preparation also fails on missing manifest-listed files, JSONL sort/key-order drift, unknown labels, and generated files larger than the configured threshold.
- Add optional S3 audit upload support with a configurable `RELEASE_AUDIT_S3_PREFIX`.
- `publish-dataset` accepts the configured committed prerelease or release snapshot as input and stages the Hugging Face payload. It still needs support for recording the published Hugging Face revision in the manifest/config.
