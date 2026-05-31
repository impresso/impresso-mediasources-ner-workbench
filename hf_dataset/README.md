---
language:
- fr
- de
- lb
task_categories:
- token-classification
pretty_name: Impresso Media Sources Dataset
---

# Impresso Media Sources Dataset

Source card for the future Hugging Face training dataset.

This dataset will contain curated JSONL records for cited news-agency and radio-station source mentions in Impresso newspaper articles.

The published data files should follow the usual Hugging Face JSON layout:

```text
data/train.jsonl
data/validation.jsonl
data/test.jsonl
label_map.json
```

Each JSONL row represents one document/article. The main columns are intended to be easy to load with `datasets` and easy to inspect in the Hub viewer:

- `id`, `language`, `newspaper`, `date`, `year`, `document_id`
- `text`
- `tokens`
- `token_start_offsets`, `token_end_offsets`
- `token_labels`, `token_label_ids`
- `token_nel`, `token_ocr`, `token_render`, `token_segment_ids`
- `segments`, `sentences`
- `entities`
- `quality_flags`

The canonical annotations are the BIO labels in `token_labels` plus the resolved span records in `entities`. Richer conversion/debug information from legacy HIPE TSV files should be published only as optional audit artifacts, not as the primary training format.

The source copy of this card lives in the workbench. Publishing scripts should copy it into the Hugging Face dataset repository.
