# Dataset Extension Plan

The workbench supports two different dataset extension axes. Keep them separate in planning, state summaries, review queues, and release notes.

## 1. Horizontal Extension: More Documents

Horizontal extension adds more examples for the current annotation scope.

Use it when the existing label space is under-covered, for example too few French `org.ent.pressagency.reuters` examples or too few German radio-station examples.

Typical workflow:

```text
sample candidates
  -> pre-annotate known media-source labels
  -> review sampled spans
  -> export train/test JSONL
  -> refresh prerelease
```

Primary commands:

```bash
make annotation-stats CFG=configs/model-v2.0.0.mk
make sample-needed-newsagencies CFG=configs/model-v2.0.0.mk
make score-newsagency-snippets CFG=configs/model-v2.0.0.mk
make review-newsagency-snippets CFG=configs/model-v2.0.0.mk REVIEWER="$USER"
make export-newsagency-snippets CFG=configs/model-v2.0.0.mk
```

Track:

- documents added
- entities added
- label/language coverage
- sampled/scored/reviewed/exported counts
- train/validation/test split impact

## 2. Vertical Extension: More Entity Types Or Deeper Annotation

Vertical extension adds annotation depth inside documents that are already in scope. Newspaper mentions are the main expected example.

Use it when the semantic scope grows, for example adding `org.ent.newspaper.<canonical_id>` mentions to documents that already contain news-agency or radio-station annotations.

Prefer entity-first review:

```text
choose target entity or entity family
  -> generate candidate spans in existing JSONL
  -> review one target at a time
  -> apply accepted span patches
  -> refresh prerelease
```

For newspaper mentions, this means passes such as:

```text
NZZ candidates -> review NZZ spans -> apply NZZ patches
Gazette de Lausanne candidates -> review GDL spans -> apply GDL patches
...
```

This keeps the reviewer focused on one label policy at a time and makes consistency easier than document-first review over many newspaper labels.

## Generic Span-Patch Workflow

Vertical extension and missed-annotation repair share one generic abstraction: a candidate span patch.

```text
audit candidates
  -> span-patch review queue
  -> append-only decisions
  -> apply accepted/corrected patches to JSONL
  -> prerelease update
```

Current commands:

```bash
make audit-empty-training-docs CFG=configs/model-v2.0.0.mk
make review-span-patches CFG=configs/model-v2.0.0.mk REVIEWER="$USER"
make apply-span-patches CFG=configs/model-v2.0.0.mk
```

The defaults point at the active v2.0.0 prerelease empty-training-doc audit. For another audit source, override:

```bash
make review-span-patches \
  CFG=configs/model-v2.0.0.mk \
  SPAN_PATCH_AUDIT_ID=newspapers-nzz-v2.0.0 \
  SPAN_PATCH_CANDIDATES=audit.d/newspapers/nzz/candidates.jsonl \
  SPAN_PATCH_TARGET_LABEL=org.ent.newspaper.nzz \
  REVIEWER="$USER"
```

Then apply accepted decisions:

```bash
make apply-span-patches \
  CFG=configs/model-v2.0.0.mk \
  SPAN_PATCH_AUDIT_ID=newspapers-nzz-v2.0.0 \
  SPAN_PATCH_CANDIDATES=audit.d/newspapers/nzz/candidates.jsonl \
  SPAN_PATCH_SOURCE_JSONL=data/prereleases/dataset-v2.0.0/train.jsonl \
  SPAN_PATCH_OUTPUT_JSONL=data/curated/span-patches/newspapers-nzz-v2.0.0/patched-train.jsonl \
  SPAN_PATCH_TARGET_LABEL=org.ent.newspaper.nzz
```

Decision files are append-only and stay under ignored local curation paths by default:

```text
data/curated/span-patches/<audit-id>/decisions.jsonl
```

Each decision is anchored by stable document ID and character offsets, not by transient token IDs. Token labels are rebuilt from the resulting entity spans when patches are applied.

Audit review uses the same curator vocabulary across entity families:

- `accept`: add the suggested span.
- `reject`: verify that the suggestion is a false positive.
- `skip`: leave the suggestion unresolved.
- `modify`: correct the span and/or label before applying it.

Accepted, rejected, and modified suggestions receive a local audit marker:

```text
USER:DATE:verified
```

Verified suggestions are suppressed from later queues with the same stable review ID. This keeps repeated audit passes focused on new or unresolved suspicious entities.

When decisions are applied, the public JSONL receives reviewer-neutral `audit_marks` for verified suggestions. These marks persist through release publication and allow later audits to suppress the same verified span/label without publishing reviewer names.

## Release Rule

Do not mix the two extension axes in release notes or review summaries.

For every prerelease update, state whether it contains:

- horizontal extension: more documents/examples for existing labels
- vertical extension: deeper annotation or new entity families in existing documents
- repair: missed-span fixes found by audit

The same prerelease may contain more than one category, but the counts should be reported separately.

Major dataset versions follow entity-family scope:

- `v1.x.x`: press agencies.
- `v2.x.x`: press agencies and radio stations.
- `v3.x.x`: press agencies, radio stations, and newspapers.
