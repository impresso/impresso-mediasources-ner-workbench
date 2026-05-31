# Annotation Guidelines

These guidelines define how to annotate news-agency and radio-station source mentions for the Impresso media sources dataset.

The dataset trains one joint token-classification model with two entity families:

- `org.ent.pressagency.<canonical_id>`
- `org.ent.radiostation.<canonical_id>`

Annotators work on sampled search results and short paragraph-sized contexts, not complete long articles. The goal is to capture explicit source attributions cleanly while keeping the annotation task fast and consistent.

## Core Task

Annotate a news agency or radio station only when the organization is presented as the source, sender, broadcaster, cited origin, or transmission channel for the reported information.

Typical positive contexts:

- `Reuters meldet ...`
- `Selon l'agence Havas ...`
- `D.N.B. berichtet ...`
- `Radio Londres annonce ...`
- `Nach einer Meldung der BBC ...`
- `Le poste de Moscou diffuse ...`

Typical negative contexts:

- an article about Reuters, BBC, or another organization as a topic
- a business story about an agency merger or office
- a programme schedule where a radio station is not the cited source of news
- a generic phrase such as `une agence`, `ag.`, or `Agentur` without a resolved real organization
- an author signature or correspondent attribution

The annotation target is the source mention, not the whole sentence and not the article.

## Annotation Unit

The new workflow annotates short contexts sampled from search results:

- Prefer one paragraph or a compact paragraph window around the search hit.
- Include enough surrounding text to decide whether the mention is a source attribution.
- Do not require the full article unless the short context is ambiguous.
- If the search hit is in a title or dateline, include the following paragraph when possible.
- If a paragraph contains multiple source mentions, annotate all accepted mentions in that paragraph.
- If the paragraph contains no accepted source mention, keep it as a negative example when it is useful for disambiguation.

The paragraph is the training row source. Metadata must still preserve the original article/document ID, newspaper/media ID, date, language, search query, search hit, and paragraph offsets where available.

## Entity Families

### News Agencies

Use `org.ent.pressagency.<canonical_id>` for real news agencies and press agencies.

Examples:

- Reuters
- Havas
- Agence France-Presse / AFP
- Associated Press / AP
- United Press / UPI
- Deutsches Nachrichtenbüro / DNB
- Deutsche Presse-Agentur / DPA
- TASS
- Wolff

Only labels backed by canonical metadata in `resources/newsagency_seeds.json` are trainable labels.

### Radio Stations

Use `org.ent.radiostation.<canonical_id>` for real radio stations or broadcasters when they are cited as the source or broadcaster of information.

Examples:

- BBC
- Radio Londres
- Radio Paris
- Radio Moscou / Radio Moscow
- Voice of America
- Radio Free Europe
- Deutsche Welle

Do not annotate every radio-station mention. Annotate only source-like uses: broadcasts, announcements, reports, bulletins, monitored radio news, or cited radio messages.

## Positive And Negative Decisions

### Annotate

Annotate when the context means that the information comes from the agency or station:

- source verbs: `meldet`, `berichtet`, `annonce`, `communique`, `déclare`, `diffuse`, `broadcasts`, `reports`
- source nouns: `Meldung`, `dépêche`, `communiqué`, `bulletin`, `émission`, `broadcast`
- dateline/source formulas: `(Reuter)`, `(Havas)`, `(D.N.B.)`, `Radio Londres:`
- indirect source attribution: `nach Reuter`, `selon Havas`, `d'après la BBC`

### Do Not Annotate

Do not annotate when the organization is only discussed as an institution:

- `Reuters eröffnet ein Büro ...`
- `La BBC emploie ...`
- `L'agence Havas fut critiquée ...`

Do not annotate when the mention is too generic:

- `ag.`
- `agence`
- `Agentur`
- `bureau`
- `correspondance`

Do not annotate author/correspondent signatures:

- `sn`
- initials or reporter names
- old `pers.ind.articleauthor` cases from the thesis data

Do not annotate unresolved unknowns as labels. Mark them for review if they might be resolvable; otherwise they become negative/O tokens.

## Boundaries

Annotate the shortest complete organization mention.

Include:

- abbreviation-internal periods: `D.N.B.`, `A.F.P.`
- abbreviation-internal hyphens or slashes when part of the name: `ATS-SDA`, `Kipa/Apic`
- words that are part of the official name: `Agence France Presse`, `United Press`
- OCR-noisy characters that belong to the mention if the mention is still identifiable

Exclude:

- sentence-final periods after a name: annotate `Havas`, not `Havas.`
- surrounding parentheses, brackets, quotation marks, commas, dashes, or colons
- generic words unless they are part of the proper name
- article titles or sentence context outside the name

German compounds:

- Annotate only the agency-name part when possible: `Reuter` in `Reutermeldung`.
- If the annotation tool cannot select a substring inside a token, flag the case for review instead of expanding to a misleading full compound label.

Radio-station names:

- Include `Radio` when it is part of the station name: `Radio Paris`, `Radio Moscou`.
- For `BBC`, annotate the acronym alone unless the full name is present.
- Do not include words like `poste`, `sender`, or `station` unless they are part of the name or needed to identify a historical station label.

## OCR And Normalization

Historical OCR is noisy. Keep the surface form as printed/OCRed, but record corrections when the mention is identifiable.

Rules:

- Annotate noisy but identifiable mentions.
- Store the corrected form in the annotation metadata when available.
- Do not create a new label for an OCR variant.
- If OCR noise makes the organization impossible to identify, do not assign a canonical label.
- If the mention boundary is uncertain but the organization is clear, select the best surface span and flag the row for review.

Examples:

- `Reutei` may be annotated as Reuters with normalized surface `Reuter` or `Reuters`.
- `D . N . B .` should normalize to `D.N.B.` if offsets can still be preserved.
- `B. N.` should not be guessed as a real agency unless the context makes it clear.

## Labels And Exclusions

Trainable labels must be canonical real organizations.

Allowed label families:

- `org.ent.pressagency.<canonical_id>`
- `org.ent.radiostation.<canonical_id>`

Forbidden as trainable labels:

- `unk`
- `org.ent.pressagency.unk`
- unresolved `ag`
- `org.ent.pressagency.ag`
- `pers.ind.articleauthor`
- generic organization labels
- generic source markers without a resolved organization

If a mention is real but the canonical label is missing, use a review status rather than inventing a label. Add or update canonical metadata before it becomes trainable.

## Paragraph-Level Sampling Workflow

The new workflow starts from targeted search results, not whole-document annotation.

Recommended workflow:

1. Search for aliases, abbreviations, historical spellings, and OCR variants.
2. Sample search hits by entity, language, decade, newspaper/media source, and query variant.
3. Extract a paragraph-sized context around each hit.
4. Annotate accepted source mentions in that paragraph.
5. Mark hard negatives where the alias appears but is not a source mention.
6. Record the decision status, query provenance, and metadata.
7. Run an alias-based missed-mention audit over the paragraph before export.

Keep negative examples. They are especially important for short acronyms and radio-station names:

- `AP` as a non-agency acronym
- `ATP`, `FN`, or sports abbreviations
- BBC as an institution rather than a source
- radio station schedule mentions
- generic `ag.`, `agence`, `Agentur`

## Quality Statuses

Each paragraph candidate should receive a curation status:

| Status | Meaning | Training use |
| --- | --- | --- |
| `accepted` | Contains one or more verified source mentions. | Include. |
| `negative` | Contains no source mention but is useful contrastive material. | Include as all-`O`. |
| `review` | Potential mention needs a decision or canonical metadata update. | Exclude until resolved. |
| `non_usable` | Too noisy, too little context, wrong language, or broken OCR. | Exclude. |

Use `review` for ambiguous historical labels rather than forcing uncertain annotations.

## Differences From The MA Thesis Guidelines

The new guidelines keep the central semantic rule from the MA thesis: annotate explicit source attributions, not all organization mentions.

Important continuities:

- The source-attribution definition remains the core rule.
- OCR-noisy but identifiable mentions should be retained with correction metadata.
- Abbreviation-internal periods remain part of the mention.
- Sentence-final punctuation remains outside the mention.
- Generic words like `agence` or `Agentur` are excluded unless part of a proper name.
- German compounds should not be over-annotated.
- Author attributions are not target entities.

Important changes:

- The new dataset includes both news agencies and radio stations in one model.
- Radio stations are first-class labels only when they function as cited information sources or broadcasters.
- Annotation is paragraph-centered, not full-document-centered.
- The workflow begins from sampled search results and query provenance.
- Negative paragraph examples are deliberately curated for disambiguation.
- `unk` is no longer a trainable label.
- Bare `ag` is no longer a trainable news-agency label.
- `pers.ind.articleauthor` is excluded rather than modeled as a disambiguation tag.
- The primary data format is Hugging Face-style JSONL, not HIPE TSV.
- Entity spans must support both token-level BIO labels and character offsets in paragraph text.

The practical consequence is that annotators should spend less time deciding full-article usability and more time making precise paragraph-level source/negative decisions.

## Examples

| Text | Decision | Span | Label |
| --- | --- | --- | --- |
| `Selon Reuters, la situation reste confuse.` | annotate | `Reuters` | `org.ent.pressagency.reuters` |
| `Reuters ouvre un nouveau bureau.` | do not annotate | none | all `O` |
| `D.N.B. meldet aus Berlin ...` | annotate | `D.N.B.` | `org.ent.pressagency.dnb` |
| `Nach einer Sendung der BBC ...` | annotate | `BBC` | `org.ent.radiostation.bbc` |
| `La BBC modifie son programme.` | do not annotate | none | all `O` |
| `ag. meldet ...` | do not label as agency | none | all `O`, possible review |
| `sn` as a signature | do not annotate | none | all `O` |
