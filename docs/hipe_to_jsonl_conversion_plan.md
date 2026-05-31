# HIPE TSV To JSONL Conversion Plan

This plan describes how to convert the original HIPE/CLEF-style TSV files from the historical news-agency classifier into the new Hugging Face-friendly JSONL format.

The conversion has two goals:

1. Preserve useful multilingual annotation, metadata, offsets, OCR evidence, and entity links.
2. Remove legacy categories that are not real news agencies from the public training labels.

The target field contract is defined in [jsonl_schema.md](jsonl_schema.md).

## Inputs

Authoritative legacy annotated files:

```text
newsagency-classification-main-nikki/data/annotated_data/de/newsagency-data-train-de.tsv
newsagency-classification-main-nikki/data/annotated_data/de/newsagency-data-dev-de.tsv
newsagency-classification-main-nikki/data/annotated_data/de/newsagency-data-test-de.tsv
newsagency-classification-main-nikki/data/annotated_data/fr/newsagency-data-train-fr.tsv
newsagency-classification-main-nikki/data/annotated_data/fr/newsagency-data-dev-fr.tsv
newsagency-classification-main-nikki/data/annotated_data/fr/newsagency-data-test-fr.tsv
```

Ignore the legacy `annotated_data/multilingual/` files for the main import. They are derived convenience files, not the complete authoritative source set: the multilingual train file corresponds to `de/train` plus `fr/train`, the multilingual dev file corresponds to `de/dev`, and the multilingual test file corresponds to `fr/test`. Using only the multilingual files would omit `fr/dev` and `de/test`.

Expected HIPE columns:

```text
TOKEN NE-COARSE-LIT NE-COARSE-METO NE-FINE-LIT NE-FINE-METO NE-FINE-COMP NE-NESTED NEL-LIT NEL-METO RENDER SEG OCR-INFO MISC
```

Expected document comments:

- `# language = ...`
- `# newspaper = ...`
- `# date = ...`
- `# document_id = ...`
- `# news-agency-as-source = ...`
- `# segment_iiif_link = ...`
- `# global.columns = ...`

## Outputs

Primary Hugging Face dataset files:

```text
data/curated/legacy-import/train.jsonl
data/curated/legacy-import/validation.jsonl
data/curated/legacy-import/test.jsonl
data/curated/legacy-import/label_map.json
data/curated/legacy-import/conversion_report.json
```

Audit files:

```text
data/curated/legacy-import/audit/train.audit.jsonl
data/curated/legacy-import/audit/validation.audit.jsonl
data/curated/legacy-import/audit/test.audit.jsonl
data/curated/legacy-import/audit/excluded_entities.jsonl
```

The public training files must contain only accepted real-agency labels. Removed or unresolved legacy labels are recorded in audit files.

## Label Policy

### Accepted Legacy Agency Labels

The converter should accept historical labels only if they resolve to trainable entries in `resources/newsagency_seeds.json`.

Observed accepted label bases include:

```text
org.ent.pressagency.AFP
org.ent.pressagency.ANSA
org.ent.pressagency.AP
org.ent.pressagency.APA
org.ent.pressagency.ATS-SDA
org.ent.pressagency.Belga
org.ent.pressagency.CTK
org.ent.pressagency.DDP-DAPD
org.ent.pressagency.DNB
org.ent.pressagency.DPA
org.ent.pressagency.Domei
org.ent.pressagency.Europapress
org.ent.pressagency.Extel
org.ent.pressagency.Havas
org.ent.pressagency.Kipa
org.ent.pressagency.Reuters
org.ent.pressagency.SPK-SMP
org.ent.pressagency.Stefani
org.ent.pressagency.TASS
org.ent.pressagency.UP-UPI
org.ent.pressagency.Wolff
org.ent.pressagency.Xinhua
```

Canonical JSONL span labels should be lowercase IDs from the seed metadata, for example:

```text
org.ent.pressagency.AFP      -> org.ent.pressagency.afp
org.ent.pressagency.UP-UPI   -> org.ent.pressagency.up-upi
org.ent.pressagency.ATS-SDA  -> org.ent.pressagency.ats-sda
```

`token_labels` keep BIO prefixes over the canonical label:

```text
B-org.ent.pressagency.up-upi
I-org.ent.pressagency.up-upi
```

### Removed Legacy Categories

The following legacy labels are not trainable labels in the new public dataset:

| Legacy label family | Reason | Public JSONL action | Audit action |
| --- | --- | --- | --- |
| `org.ent.pressagency.unk` | Unknown unresolved agency; not a real canonical label. | Replace covered tokens with `O`. | Record original span in `excluded_entities.jsonl` with reason `unknown_agency`. |
| `org.ent.pressagency.ag` | Generic agency/source marker, not a specific real news agency. | Replace covered tokens with `O`. | Record original span with reason `generic_agency_marker`. |
| `pers.ind.articleauthor` | Author attribution, not a news agency. | Replace covered tokens with `O`. | Record original span with reason `article_author`. |
| Any label not present in seed metadata | Unapproved or unresolved label. | Fail by default, or exclude with explicit `--unknown-label-policy exclude`. | Record original span with reason `unknown_label`. |
| Malformed BIO sequence | Cannot be trusted as-is. | Repair only if unambiguous; otherwise replace affected span with `O`. | Record diagnostic with reason `malformed_bio`. |

The default mode should be conservative:

```text
--forbidden-label-policy exclude
--unknown-label-policy error
--malformed-bio-policy error
```

For exploratory imports, allow:

```text
--unknown-label-policy exclude
--malformed-bio-policy repair
```

Any excluded token must receive `O` in `token_labels` and ID `0` in `token_label_ids`.

## Conversion Stages

### 1. Discover Inputs

- Accept one or more input files or directories.
- Expand directories recursively for `*.tsv`.
- Determine candidate split from filename:
  - `train` -> `train`
  - `dev` -> `validation`
  - `test` -> `test`
- Allow `--split train|validation|test` for fixture or one-off imports where the filename does not encode the split.
- Keep `source_file` relative to the configured source root.
- Detect duplicate `document_id` values within the monolingual source set before writing output.

Duplicate handling policy:

- If duplicate rows are byte-identical after conversion, keep one and record the duplicate in the report.
- If duplicate `document_id` rows differ, fail and require manual selection.
- The current monolingual source set contains repeated identical records in some files; use `--duplicate-policy keep-first` for the first import.

### 2. Parse HIPE Documents

- Read comments and token rows as a document stream.
- Validate `# global.columns` against the expected 13-column layout.
- Preserve unknown comments in the audit record.
- Track the active `segment_iiif_link` and assign segment IDs to following tokens.
- Require `language`, `newspaper`, `date`, and `document_id`; missing values should fail unless `--allow-missing-metadata` is set.
- If `language` is absent in legacy multilingual files, infer it from monolingual path components or known legacy newspaper IDs and add `inferred_language` to `quality_flags`.

### 3. Reconstruct Text And Offsets

- Reconstruct normalized `text` from `TOKEN` and `RENDER`.
- Insert a single space after a token by default.
- Suppress the following space when `RENDER` contains `NoSpaceAfter`.
- Treat `EndOfLine` as layout evidence; preserve it only in audit `layout_text`.
- Record `token_start_offsets` and `token_end_offsets`.
- Build `segments` from active IIIF links and `sentences` from `SEG = EndOfSentence`.
- Verify `text[start:end] == token` for every token.

### 4. Convert BIO Labels

- Read token labels from `NE-FINE-LIT`.
- Normalize `_` and empty values to `O`.
- Convert only accepted real-agency labels to canonical labels.
- Replace forbidden categories with `O` in the public row.
- Merge accepted BIO spans into `entities`.
- Preserve original labels in `entities[].label_original`.
- Preserve QIDs from `NEL-LIT` as `token_nel` and entity-level `nel`.

BIO repair rules:

- `I-X` following `B-X` or `I-X` continues the span.
- `I-X` after `O` is malformed. In strict mode, fail. In repair mode, treat it as `B-X` and add `repaired_bio` to `quality_flags`.
- `I-X` after a different label is malformed. In strict mode, fail. In repair mode, close the previous span and start a new one.

### 5. Parse OCR Evidence

- Copy raw `OCR-INFO` into `token_ocr`.
- Parse `LED...` values where possible.
- Parse transcript corrections from values like `Transcript:Reuter|LED0.17`.
- Add entity-level:
  - `has_ocr_correction`
  - `max_ocr_levenshtein`
  - `normalized_surface` when transcript evidence provides a useful correction
- Add `has_ocr_corrections` to `quality_flags` when any token has transcript correction or non-zero LED.

### 6. Generate Label Map

- Collect canonical public `token_labels` across all splits.
- Force `O` to ID `0`.
- Sort remaining labels deterministically by canonical label, with `B-` before `I-`.
- Write `label_map.json`.
- Fill `token_label_ids` after the final map is known.
- Validate that no forbidden label appears in `label_map.json`.

### 7. Write Primary JSONL

Write one row per document into split-specific files:

- `train.jsonl`
- `validation.jsonl`
- `test.jsonl`

Each row must follow [jsonl_schema.md](jsonl_schema.md). Public rows should not contain original token-column dictionaries or excluded entity details.

### 8. Write Audit JSONL

For every converted document, write an audit row with:

- all original token columns
- raw comments
- `layout_text`
- converter version
- conversion timestamp
- input file and line span
- excluded entity spans and reasons
- BIO repair diagnostics

Also write `audit/excluded_entities.jsonl`, one row per removed span:

```json
{
  "document_id": "DTT-1945-08-09-a-i0008",
  "split": "validation",
  "language": "de",
  "source_file": "data/annotated_data/de/newsagency-data-dev-de.tsv",
  "reason": "unknown_agency",
  "label_original": "org.ent.pressagency.unk",
  "surface": "Pm",
  "token_start": 42,
  "token_stop": 43,
  "start": 250,
  "stop": 252,
  "nel": "",
  "ocr_info": ["Transcript:B. N.|LED1.00"]
}
```

### 9. Validate Outputs

Validation checks:

- required fields are present
- array lengths match token count
- all offsets are valid
- token offsets match token text
- entity offsets match entity surface
- entity token spans match token labels
- `token_label_ids` match `label_map.json`
- forbidden labels are absent from `token_labels`, `entities[].label`, and `label_map.json`
- `language`, `newspaper`, `date`, and `document_id` are present
- no split leakage through duplicate `document_id`
- no unresolved label remains outside audit files

Write `conversion_report.json` with:

- input files
- converted document counts by split and language
- token counts by split and language
- accepted entity counts by label, split, and language
- removed entity counts by reason, original label, split, and language
- duplicate document diagnostics
- missing metadata diagnostics
- malformed BIO diagnostics
- OCR correction counts
- IIIF segment counts and missing-link counts

### 10. Manual Review Gate

Before publishing converted data:

- Review `audit/excluded_entities.jsonl`.
- Confirm that `unk` spans cannot be resolved to real agencies.
- Confirm that `ag` spans are truly generic source markers, not abbreviations for a real agency.
- Confirm that all accepted labels have seed metadata, Wikidata URLs where available, and Wikipedia URLs where available.
- Confirm language and split counts against the original thesis statistics.
- Freeze `label_map.json`.

## Proposed Command

Public workbench entry point:

```bash
make import-legacy-hipe ARGS="\
  --input ../newsagency-classification-main-nikki/data/annotated_data/de \
  --input ../newsagency-classification-main-nikki/data/annotated_data/fr \
  --source-root ../newsagency-classification-main-nikki \
  --output data/curated/legacy-import \
  --newsagency-seeds resources/newsagency_seeds.json \
  --forbidden-label-policy exclude \
  --unknown-label-policy error \
  --malformed-bio-policy error \
  --duplicate-policy keep-first"
```

Implementation module:

```bash
python -m lib.import_legacy_hipe_tsv \
  --input ... \
  --output ... \
  --newsagency-seeds ...
```

## Implementation Checklist

- [ ] Add `lib/import_legacy_hipe_tsv.py`.
- [ ] Add a parser for document comments and 13-column token rows.
- [ ] Add deterministic split detection and `dev` to `validation` mapping.
- [ ] Add `--split` override for fixtures and one-off imports.
- [ ] Add duplicate document detection with `error` and `keep-first` modes.
- [ ] Add language inference for legacy multilingual files that lack `# language`.
- [ ] Add text reconstruction and offset generation.
- [ ] Add BIO span conversion and canonical label normalization.
- [ ] Add forbidden-label removal for `unk`, `ag`, and `pers.ind.articleauthor`.
- [ ] Add audit output for removed categories.
- [ ] Add `label_map.json` generation.
- [ ] Add primary split JSONL writers.
- [ ] Add `conversion_report.json`.
- [ ] Add fixtures covering accepted labels, `unk`, `ag`, author labels, OCR transcripts, `NoSpaceAfter`, `EndOfLine`, and malformed BIO.
- [ ] Add `make import-legacy-hipe`.
- [ ] Add validation tests that forbidden labels never appear in public outputs.
