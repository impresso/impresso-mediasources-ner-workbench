---
language:
- fr
- de
task_categories:
- token-classification
tags:
- historical-newspapers
- named-entity-recognition
- impresso
pretty_name: Impresso Media Sources Dataset
license: other
---

# Impresso Media Sources Dataset

Curated token-classification data for news-agency and radio-station mentions in Impresso historical newspaper text.

The v0.1 data is derived from the legacy French/German HIPE-style news-agency annotations, converted to JSONL, manually reviewed against the current model's dev/test disagreements, and updated according to annotation guidelines v2.0. The current guidelines annotate every explicit canonical media-source organization mention, not only source-attribution uses.

## Files

```text
data/train.jsonl
data/validation.jsonl
data/test.jsonl
label_map.json
dataset_summary.json
audit/curation_summary.json
audit/curation_changes.jsonl
audit/curation_changes_tags.tsv
```

Each JSONL row represents one document/article. The published `data/*.jsonl` files intentionally use a compact training schema rather than the full converted HIPE payload, so they are easy to load with `datasets` and inspect in the Hub viewer:

- `id`, `language`, `newspaper`, `date`, `year`, `document_id`
- `text`
- `tokens`
- `token_start_offsets`, `token_end_offsets`
- `token_labels`, `token_label_ids`
- `entities`
- `quality_flags`
- `legacy`

The canonical annotations are the BIO labels in `token_labels` plus the resolved span records in `entities`. The row-level `legacy` object is only for tracing back to the converted HIPE source and may contain `source_format`, `source_file`, and the original `news_agency_as_source` values. The latter is historical provenance from the thesis-era annotation semantics and should not be treated as the current target annotation.

Important metadata fields:

- `newspaper`: source newspaper/media identifier from the original annotation metadata, for example `DTT`.
- `legacy.source_format`: original annotation format, for example `hipe-tsv`.
- `legacy.source_file`: original converted annotation file, for example `data/annotated_data/de/newsagency-data-dev-de.tsv`.
- `legacy.news_agency_as_source`: document-level source-attribution QIDs from the thesis-era HIPE metadata. This is provenance only; the current gold annotation is in `token_labels` and `entities`.
- `quality_flags`: non-fatal import or curation warnings. `has_forbidden_legacy_labels` means the original row contained labels excluded by the current label policy, such as `unk`, unresolved `ag`, or `pers.ind.articleauthor`; these labels were removed from the trainable annotation.

Fields intentionally excluded from the public training rows:

- `token_nel`, `token_ocr`, `token_render`, `token_segment_ids`: token-level HIPE side channels used for conversion/debugging, not model training.
- `segments`: segment and IIIF metadata; useful for traceability, too large for the primary training table.
- `sentences`: derived sentence spans; redundant for current token-window training.
- `entities[].label_original` and `entities[].status`: legacy normalization/audit fields; the current label is `entities[].label`.

`audit/curation_changes_tags.tsv` is a compact CoNLL-like review file with `TOKEN`, `BEFORE_NERTAG`, and `AFTER_NERTAG` columns for the manually reviewed changes. It is intended for human audit, not model training.

## Loading

```python
from datasets import load_dataset

dataset = load_dataset(
    "impresso-project/impresso-mediaagencies-ner-dataset",
    data_files={
        "train": "data/train.jsonl",
        "validation": "data/validation.jsonl",
        "test": "data/test.jsonl",
    },
)
```

## Label Policy

Trainable labels use two namespaces:

- `org.ent.pressagency.<canonical_id>`
- `org.ent.radiostation.<canonical_id>`

Forbidden legacy labels such as `unk`, unresolved bare `ag`, `org.ent.pressagency.ag`, and `pers.ind.articleauthor` are excluded from the trainable label space.

The source copy of this card lives in the workbench. Publishing scripts copy it into the Hugging Face dataset repository.

## License

License metadata is set to `other` until the final redistribution terms for the converted annotations and Impresso text snippets are confirmed.
