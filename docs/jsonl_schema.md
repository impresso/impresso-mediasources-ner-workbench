# Media Sources JSONL Schema

This document defines the JSONL format for annotated media-source training and evaluation data. The published Hugging Face `data/*.jsonl` files use a compact training schema. The local conversion/import files may contain additional HIPE trace fields for debugging and audit.

For the concrete migration workflow, see [hipe_to_jsonl_conversion_plan.md](hipe_to_jsonl_conversion_plan.md).

## Dataset Layout

Publish split-specific JSONL files:

```text
data/train.jsonl
data/validation.jsonl
data/test.jsonl
label_map.json
```

Each JSONL line is one document/article. The authoritative annotation is represented twice:

- token-level BIO tags in `token_labels`
- resolved character-span annotations in `entities`

The token-level representation is convenient for Hugging Face token-classification training. The span representation is convenient for JSONL inference, manual QA, and entity-level scoring.

## Row Example

```json
{
  "schema_version": "mediasources-jsonl-v0.1",
  "id": "DTT-1945-08-09-a-i0008",
  "split": "validation",
  "language": "de",
  "newspaper": "DTT",
  "date": "1945-08-09",
  "year": 1945,
  "document_id": "DTT-1945-08-09-a-i0008",
  "text": "United Preß meldet ...",
  "tokens": ["United", "Preß", "meldet", "..."],
  "token_start_offsets": [0, 7, 13, 20],
  "token_end_offsets": [6, 12, 19, 23],
  "token_labels": [
    "B-org.ent.pressagency.up-upi",
    "I-org.ent.pressagency.up-upi",
    "O",
    "O"
  ],
  "entities": [
    {
      "token_start": 0,
      "token_stop": 2,
      "start": 0,
      "stop": 12,
      "surface": "United Preß",
      "label": "org.ent.pressagency.up-upi",
      "entity_family": "pressagency",
      "wikidata_url": "https://www.wikidata.org/wiki/Q493845",
      "ocr_correction": {
        "surface": "United Press",
        "max_levenshtein": 0.17
      }
    }
  ],
  "quality_flags": [],
  "legacy": {
    "source_format": "hipe-tsv",
    "source_file": "data/annotated_data/de/newsagency-data-dev-de.tsv",
    "source_file": "data/annotated_data/de/newsagency-data-dev-de.tsv"
  }
}
```

## Top-Level Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schema_version` | string | yes | Schema identifier, initially `mediasources-jsonl-v0.1`. |
| `id` | string | yes | Stable document ID. Prefer the Impresso content item ID or HIPE `document_id`. |
| `split` | string | yes | `train`, `validation`, or `test`. Legacy `dev` maps to `validation`. |
| `language` | string | yes | ISO-style language code from HIPE `# language = ...` or Impresso metadata. |
| `newspaper` | string | yes | Newspaper or media identifier, from HIPE `# newspaper = ...` when imported. |
| `date` | string | yes | Document date as `YYYY-MM-DD` when known. |
| `year` | int | yes | Four-digit year derived from `date`. |
| `document_id` | string | yes | Original document ID from the source annotation. May equal `id`. |
| `text` | string | yes | Normalized model text. All character offsets point into this field. |
| `tokens` | list[string] | yes | Source tokens after HIPE import or workbench tokenization. |
| `token_start_offsets` | list[int] | yes | Inclusive token start offsets into `text`. |
| `token_end_offsets` | list[int] | yes | Exclusive token end offsets into `text`. |
| `token_labels` | list[string] | yes | BIO labels aligned with `tokens`. |
| `entities` | list[object] | yes | Accepted canonical entity spans. |
| `audit_marks` | list[object] | no | Reviewer-neutral verified audit markers for accepted, modified, or rejected suspicious spans. Used to avoid repeatedly suggesting the same audited span in later audit passes. |
| `quality_flags` | list[string] | no | Non-fatal warnings such as `has_ocr_corrections` or `has_forbidden_legacy_labels`. |
| `legacy` | object | no | Minimal trace-back metadata from the original HIPE import, currently `source_format` and `source_file`. The field name is kept for compatibility; it refers to source provenance, not obsolete data. Not part of the training contract. |

The array fields `tokens`, `token_start_offsets`, `token_end_offsets`, and `token_labels` must have exactly the same length. Integer label IDs are derived from `token_labels` and `label_map.json` by training code when needed.

## Entity Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `token_start` | int | yes | Inclusive start token index. |
| `token_stop` | int | yes | Exclusive stop token index. |
| `start` | int | yes | Inclusive start character offset into `text`. |
| `stop` | int | yes | Exclusive stop character offset into `text`. |
| `surface` | string | yes | Surface form from `text[start:stop]`. |
| `label` | string | yes | Canonical span label without BIO prefix, for example `org.ent.pressagency.reuters`. |
| `entity_family` | string | yes | `pressagency` or `radiostation`. |
| `wikidata_url` | string | no | Canonical Wikidata URL when available. Raw NEL/QID provenance belongs in audit data. |
| `ocr_correction` | object | no | Present only when OCR/transcript evidence corrected the visible surface. |
| `status` | string | yes | Usually `accepted`; other statuses belong in audit files unless deliberately published. |

Public entity rows do not carry synthetic entity IDs. If a stable entity reference is needed, derive it from stable row and character-offset data such as `id`, `start`, `stop`, and `label`. Token spans are useful for training but are less stable than character offsets.

`ocr_correction` may contain:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `surface` | string | no | Corrected surface/transcript evidence when it differs from `surface`. |
| `max_levenshtein` | float | no | Maximum parsed `LED` value across the entity tokens. |

## Audit Mark Fields

`audit_marks` persists verified audit decisions in the public data without exposing reviewer names or local decision-file paths. The local append-only decision file remains the detailed provenance record.

An audit mark is not a training entity. It may describe either an accepted/modified entity suggestion or a rejected false positive.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `audit_id` | string | yes | Stable audit pass identifier, for example `empty-training-docs-v2.0.0`. |
| `status` | string | yes | Currently `verified`. |
| `decision` | string | yes | `accept`, `reject`, or `modify`. |
| `start` | int | yes | Start offset of the audited suggestion. |
| `stop` | int | yes | Stop offset of the audited suggestion. |
| `label` | string | yes | Suggested label that was audited. |
| `applied_start` | int | no | Corrected start offset when `decision` is `modify`. |
| `applied_stop` | int | no | Corrected stop offset when `decision` is `modify`. |
| `applied_label` | string | no | Corrected label when `decision` is `modify`. |

Do not publish reviewer names in `audit_marks`. If person-level provenance is needed, keep it in ignored local audit files or external audit storage.

## Segment And Sentence Fields

Segments and sentences use the same span convention:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `index` | int | yes | Zero-based segment or sentence index. |
| `iiif_link` | string | segments only | Segment-level IIIF link, when available. |
| `token_start` | int | yes | Inclusive start token index. |
| `token_stop` | int | yes | Exclusive stop token index. |
| `text_start` | int | yes | Inclusive start character offset into `text`. |
| `text_stop` | int | yes | Exclusive stop character offset into `text`. |

## Label Map

`label_map.json` fixes the integer IDs used in `token_label_ids`:

```json
{
  "label2id": {
    "O": 0,
    "B-org.ent.pressagency.reuters": 1,
    "I-org.ent.pressagency.reuters": 2
  },
  "id2label": {
    "0": "O",
    "1": "B-org.ent.pressagency.reuters",
    "2": "I-org.ent.pressagency.reuters"
  }
}
```

Rules:

- `O` must be ID `0`.
- Accepted labels use `B-` and `I-` prefixes over canonical labels.
- Canonical span labels do not include `B-` or `I-`.
- The map must not contain `*.unk`, unresolved bare `ag`, `pers.ind.articleauthor`, or generic organization labels that are not accepted media-source labels.

## Relation To HIPE TSV CoNLL Style

The historical HIPE files are CoNLL-style TSV with document metadata comments and one token per row. They begin with:

```text
# global.columns = TOKEN NE-COARSE-LIT NE-COARSE-METO NE-FINE-LIT NE-FINE-METO NE-FINE-COMP NE-NESTED NEL-LIT NEL-METO RENDER SEG OCR-INFO MISC
```

Mapping from HIPE TSV to JSONL. Targets marked `legacy` or `local import only` are preserved for traceability during conversion, but are not primary training fields in the published Hugging Face `data/*.jsonl` files. In this schema, `legacy` means HIPE source trace-back metadata retained for compatibility.

| HIPE source | JSONL target | Notes |
| --- | --- | --- |
| `# language = de` | `language` | Per-document comment is authoritative, including multilingual source files. |
| `# newspaper = DTT` | `newspaper` | Keep original media identifier. |
| `# date = 1945-08-09` | `date`, `year` | Derive `year` from `date`. |
| `# document_id = ...` | `id`, `document_id` | Use as `id` unless a better Impresso content item ID exists. |
| `# news-agency-as-source = Q...` | local import/audit only: `news_agency_as_source` | Thesis-era source-attribution provenance, not the current mention target. It is excluded from public rows because values may contain mixed QIDs and sentinels such as `_`, `unk`, and `NIL`. |
| `# segment_iiif_link = ...` | local import only: `segments[].iiif_link`, `token_segment_ids` | Applies to following tokens until the next segment link. Too large for the primary public training rows. |
| `TOKEN` | `tokens[]` | Preserve token text exactly. |
| `NE-FINE-LIT` | `token_labels[]`, `entities[]` | Main source for trainable labels. Normalize labels after import. |
| `NEL-LIT` | local import/audit only: `token_nel[]`; public entity links come from `entities[].wikidata_url` | Preserve raw QIDs in audit data; token-level arrays are conversion/debug side channels. |
| `RENDER` | local import only: `token_render[]`; public: reconstructed `text` and offsets | `NoSpaceAfter` suppresses following space. `EndOfLine` is layout evidence. |
| `SEG` | local import only: `sentences[]` | `EndOfSentence` closes a sentence span. Redundant for current token-window training. |
| `OCR-INFO` | local import/audit only: `token_ocr[]`; public: optional `entities[].ocr_correction` | Preserve raw values locally; publish compact entity-level OCR correction evidence only when present. |
| Other token columns | audit JSONL | Preserve in optional audit records if needed, not in the primary HF dataset. |
| Unknown comments | audit JSONL | Store under audit metadata rather than adding unstable public columns. |

Some historical multilingual HIPE files do not contain `# language = ...`. For those files, the importer may infer `language` from a monolingual path component or from known historical newspaper IDs. Rows with inferred language must include `inferred_language` in `quality_flags`.

## Text Reconstruction

The importer reconstructs `text` deterministically from `TOKEN` and `RENDER`:

- Start with an empty string.
- Append each token and record its start/end offsets.
- Insert a single space after a token by default.
- Do not insert a following space when `RENDER` contains `NoSpaceAfter`.
- Treat `EndOfLine` as layout evidence; official `text` should use normalized whitespace, while audit output may preserve a newline in `layout_text`.
- Trim trailing whitespace at document end and ensure token offsets still point to the exact token surfaces.

All published offsets in `token_start_offsets`, `token_end_offsets`, and `entities` refer to this normalized `text`. Local import-only `segments` and `sentences`, when present, use the same text coordinate system.

## Entity Conversion

Entity spans are built from BIO tags in `NE-FINE-LIT`:

- `B-...` starts a new entity.
- Following `I-...` tokens with the same base label extend the entity.
- Malformed BIO sequences should be flagged and either repaired conservatively or moved to audit, depending on importer policy.
- The accepted JSONL `entity.label` is the canonical label without BIO prefix.
- The accepted JSONL `token_labels` keep the BIO prefix.

Forbidden legacy labels:

- `org.ent.pressagency.unk`
- unresolved `org.ent.pressagency.ag`
- `pers.ind.articleauthor`
- generic organization labels that are not real news agencies or radio stations

These labels should not appear in the primary `token_labels`. They should become `O` or be excluded according to the import policy, with details retained in audit JSONL.

## Audit Sidecar

The main HF dataset should stay simple and stable. For reproducibility, the importer may also write audit records containing:

- original HIPE token-column dictionaries
- `layout_text`
- excluded entities and exclusion reasons
- unknown comments
- converter version and conversion date
- raw malformed BIO diagnostics

Audit files are useful for development and curation, but training and public evaluation should rely on the primary JSONL schema above.
