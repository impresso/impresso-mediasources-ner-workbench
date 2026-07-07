# Tokenization Analysis and Migration Plan

## Goal

Define one simple, entity-independent tokenization contract for sampling, annotation, dataset storage, training, evaluation, and inference.

The immediate problems are:

- French clitics are fused with following words: `l'agence` is one annotation token, so `agence` cannot be included without also including the definite article.
- Hyphens are fused inside words: `ATS-AFP` is one annotation token, so ATS and AFP cannot receive separate labels.
- A substantial v2 dataset already uses these boundaries, so changing the tokenizer requires a deterministic migration of tokens, offsets, BIO labels, entities, and pending curation artifacts.

Tokenization must not depend on the entity catalog, aliases, model predictions, language-specific entity lists, or annotation labels.

## Current Representation

### Annotation tokens

Sampled snippets use this regular expression:

```python
r"\w+(?:[-']\w+)*|[^\w\s]"
```

It produces:

| Text | Current tokens |
| --- | --- |
| `l'agence Havas` | `l'agence`, `Havas` |
| `ATS-AFP` | `ATS-AFP` |
| `Telegraphen-Union` | `Telegraphen-Union` |
| `A.F.P.` | `A`, `.`, `F`, `.`, `P`, `.` |

HIPE-derived rows preserve the source HIPE tokenization rather than applying this expression. The dataset can therefore already contain different tokenization conventions depending on provenance.

BIO labels attach to annotation tokens. A token cannot carry two entity labels and a boundary cannot occur inside a token.

### Model subtokens

The training code sends annotation tokens to the ModernBERT tokenizer with `is_split_into_words=True`. ModernBERT may divide each annotation token into several model subtokens. The gold label is assigned only to the first model subtoken; continuation subtokens receive the ignore index `-100`.

Consequences:

- Model subtokenization cannot repair an annotation boundary inside `l'agence` or `ATS-AFP`.
- Even if the model tokenizer internally separates punctuation, evaluation is projected back to the indivisible annotation token.
- Annotation tokenization remains the authoritative boundary system.

The `-100` continuation labels do not remove those subtokens from the transformer. They suppress direct token-classification loss and metric contribution, while the subtokens still participate in self-attention and can transfer lexical and contextual information into the supervised first-subtoken representation. Published work on first-subtoken labelling supports this as a viable alignment strategy.

Finer annotation tokenization is therefore not inherently harmful because it may produce more model subtokens. It can be beneficial: boundaries such as `l`, `'`, `agence` become explicit annotation decisions, and each annotation token normally contributes its own supervised first subtoken. The relevant risks are inconsistent annotation-token boundaries, changed window lengths, and incorrect BIO projection during migration, rather than subtoken over-analysis itself.

### Whitespace

Whitespace is not an annotation token. It is represented by:

- the original or normalized `text`;
- `token_start_offsets` and `token_end_offsets`;
- locally, HIPE `token_render` metadata such as `NoSpaceAfter`.

For adjacent tokens `i` and `i+1`, the exact inter-token material is:

```python
text[token_end_offsets[i]:token_start_offsets[i + 1]]
```

This preserves no space, one space, repeated spaces, or line breaks without assigning NER labels to whitespace.

The current v2 splits contain 1,073,654 annotation tokens. Among 1,070,990 inter-token gaps, 858,756 are one space and 212,224 are empty. A few gaps contain repeated spaces or newlines. Offsets are therefore necessary; reconstructing text with `' '.join(tokens)` is lossy.

## Measured v2 Impact

Across the current train, validation, and test files:

| Condition | All tokens | Entity-labelled tokens |
| --- | ---: | ---: |
| Internal apostrophe | 987 | 119 |
| Internal hyphen | 800 | 255 |
| `l'agence`/`L'agence`/`D'Agence` forms | 129 | 100 |

These are token counts, not necessarily distinct entity spans. They establish that migration is manageable but cannot be treated as a harmless tokenizer replacement. At least 374 currently labelled tokens require label projection after splitting, and some need a policy decision about punctuation or articles.

## Approved Tokenization Contract

Use one context-independent lexical rule everywhere:

```python
r"[^\W\d_]+|\d+|_+|[^\w\s]"
```

Properties:

1. Every maximal Unicode letter sequence is a token.
2. Digit runs and underscore runs are separate tokens, including at letter-number transitions.
3. Every other non-word, non-whitespace character is a separate token.
4. Whitespace is never a token and remains recoverable from text offsets.
5. Original characters are preserved; tokenization does not normalize apostrophe or hyphen variants.
6. The same function is applied regardless of language, entity type, aliases, labels, or provenance.

Examples:

| Text | Proposed tokens |
| --- | --- |
| `l'agence Havas` | `l`, `'`, `agence`, `Havas` |
| `l’agence Havas` | `l`, `’`, `agence`, `Havas` |
| `ATS-AFP` | `ATS`, `-`, `AFP` |
| `ATS–AFP` | `ATS`, `–`, `AFP` |
| `Telegraphen-Union` | `Telegraphen`, `-`, `Union` |
| `Radio-Liberty` | `Radio`, `-`, `Liberty` |
| `A.F.P.` | `A`, `.`, `F`, `.`, `P`, `.` |

The tokenizer does not decide whether punctuation belongs to an entity. That is an annotation-policy decision.

## Approved Annotation Policy

### French articles and clitics

For `l'agence Havas`, annotate `agence Havas`:

| Token | Label |
| --- | --- |
| `l` | `O` |
| `'` | `O` |
| `agence` | `B-org.ent.pressagency.havas` |
| `Havas` | `I-org.ent.pressagency.havas` |

This implements the intended boundary: include the organizational designator `agence`, exclude the definite article and its apostrophe.

The same principle should apply to case variants and Unicode apostrophes. Other contractions must be specified by grammatical function, not by a list of known entities. For example, a lexical apostrophe inside a proper name may remain part of the annotated span by labelling the apostrophe token `I-...`.

### Hyphens

For two source attributions joined typographically, annotate separate entities and leave the separator `O`:

```text
ATS       B-org.ent.pressagency.ats-sda
-         O
AFP       B-org.ent.pressagency.afp
```

For a hyphen that is part of one visible organization name, include it in one contiguous entity:

```text
Telegraphen  B-org.ent.pressagency.telegraphen-union
-            I-org.ent.pressagency.telegraphen-union
Union        I-org.ent.pressagency.telegraphen-union
```

Thus the lexical tokenizer remains simple. The curator decides whether the punctuation connects one name or separates multiple names.

### Whitespace

Whitespace remains outside BIO annotation. Entity character surfaces are derived from the first token start through the last token end, so internal whitespace remains present in `entity.surface` without becoming labelled tokens.

## Migration Design

Migration must operate from `text` and character offsets, not by splitting token strings and guessing labels.

### Canonical intermediate form

Before retokenization, convert every accepted BIO sequence into character spans:

```text
(character_start, character_stop, canonical_label)
```

The existing `entities` array may be used only after checking that it agrees with BIO labels and offsets. BIO plus offsets should remain the recoverable source when an older row lacks reliable entities.

### Retokenization

For each document:

1. Preserve `text` byte-for-byte and character-for-character.
2. Generate canonical tokens and offsets from `text` using the new rule.
3. Project character spans onto new tokens.
4. Apply explicit boundary policy transforms, such as excluding French article-plus-apostrophe from an agency span.
5. Regenerate BIO labels and `entities` from the projected spans.
6. Validate exact surface and offset agreement.

No character span may be silently expanded merely because it intersects a new token. Since the new tokenizer is finer-grained than the sampled-snippet tokenizer, most old spans can be represented exactly.

### French boundary correction

Splitting `l'agence` alone would initially project its old entity label to `l`, `'`, and `agence`. A separate deterministic annotation migration must then narrow recognized article constructions to start at `agence`.

This transform should be based on syntax visible in the span, for example:

```text
[l|L] ['|’] [agence|Agence] ...
```

It should not inspect the entity label catalog beyond confirming that the span is a press-agency annotation. Every changed span must be logged.

### Artifacts requiring migration or regeneration

- `train.jsonl`, `validation.jsonl`, and `test.jsonl`;
- snippet candidate, scored, reviewed, and exported JSONL that will remain active;
- append-only decisions whose token indices refer to old tokens;
- disagreement-review inputs and decisions;
- span-patch and existing-span audit inputs and decisions;
- ignored TSV inspection views;
- model evaluation predictions and quality reports;
- label map only if labels change, which this plan does not require.

Index-based decisions cannot simply be replayed after retokenization. They must first be materialized against the old tokenization, converted to character spans, and then migrated, or archived as evidence after their result has entered the canonical dataset.

## Compatibility and Versioning

Changing annotation tokens changes the training examples and entity boundaries even when document text and canonical labels stay unchanged. It should therefore be treated as a dataset schema/profile migration, not an in-place tokenizer tweak.

Recommended metadata:

```json
{
  "schema_version": "mediaagencies-jsonl-v0.2",
  "tokenization": "unicode-word-punctuation-v1"
}
```

The tokenizer name should be stored in every row or guaranteed by a release manifest. Mixing tokenization profiles in one release should be rejected by validation.

The current v2 prerelease can still be migrated before publication, but the migration should produce a full diff report and a reversible backup/release artifact.

## Validation Gates

Implementation should not be promoted until all of these pass:

1. Every token equals `text[start:stop]`.
2. Token offsets are ordered, non-overlapping, and cover every non-whitespace character exactly once.
3. Inter-token substrings reconstruct the original text exactly.
4. BIO arrays have the same length as tokens.
5. BIO and `entities` describe the same spans and labels.
6. No entity boundary falls inside an annotation token.
7. No overlapping entity spans are introduced.
8. Train, validation, and test document identities and split assignments are unchanged.
9. Counts of labels and changed spans are reported per split and label.
10. A focused report lists every span narrowed by the French article rule.
11. A focused report lists every old hyphenated labelled token and its new annotation.
12. Existing annotation and model tests run against the new token profile.
13. Model subtoken statistics are regenerated because annotation-word counts and window boundaries will change.

## Implementation Work Plan

### Phase 1: Specify

- Approve the canonical token rule.
- Approve the French article/clitic boundary policy.
- Approve punctuation inclusion rules for lexical organization names.
- Add a tokenization profile to the JSONL schema and annotation guidelines.

### Phase 2: Audit without mutation

- Build a dry-run analyzer for all three splits.
- Produce old/new token counts, affected documents, projected spans, narrowed spans, and ambiguous cases.
- Classify every affected entity span as exact, deterministic policy change, or manual review required.

### Phase 3: Implement and test

- Centralize the tokenizer in one module used by sampling, import normalization, review, export, and inference preparation.
- Implement character-span-based retokenization.
- Add unit tests for ASCII/Unicode apostrophes and hyphens, OCR punctuation, dotted acronyms, whitespace gaps, and BIO projection.
- Reject mixed tokenization profiles.

### Phase 4: Migrate curated state

- Materialize all accepted decisions under the old tokenization.
- Retokenize canonical train, validation, and test rows.
- Regenerate active snippet and audit artifacts where feasible; archive stale index-based queues.
- Review only the ambiguous migration report.

### Phase 5: Verify and retrain

- Regenerate TSV views, dataset statistics, subtoken statistics, and quality reports.
- Diff old and new entity character spans.
- Retrain the v2 model because annotation boundaries and model windows changed.
- Re-run validation/test evaluation and disagreement audits.

## Recommendation

Adopt the simple punctuation-splitting tokenization rule and keep whitespace exclusively in text offsets. This gives annotation enough granularity for both `agence` without `l'` and separate agencies in `ATS-AFP`, while still allowing lexical hyphenated names to be represented as one BIO span. This finer analysis should also improve supervision granularity; continuation model subtokens remain available to the transformer even where their direct loss is masked with `-100`.

The plan was approved for the v2 prerelease. Implementation must still run the Phase 2 dry-run audit before writing migrated split files, especially for the apostrophe-containing and hyphen-containing entity tokens already present in v2.

## Implementation Status

- Phase 1 complete: schema and annotation policy specify `unicode-word-punctuation-v1`.
- Phase 2 complete: the pre-migration audit is preserved with the v2 prerelease.
- Phase 3 complete: tokenization, character-span projection, French boundary normalization, and tests are centralized.
- Phase 4 complete: train, validation, test, and generated snippet splits were migrated and integrated.
- Phase 5 data verification complete: TSV views, label map, split validation, dataset statistics, and subtoken statistics were regenerated. Model retraining and post-training quality evaluation remain the next model-lifecycle step; the previous quality report is marked invalid for the migrated tokenization.
