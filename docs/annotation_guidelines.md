# Annotation Guidelines

**Version 2.0**

These guidelines define how to annotate news-agency and radio-station mentions for the Impresso media sources dataset.

The dataset trains one joint token-classification model with two entity families:

- `org.ent.pressagency.<canonical_id>`
- `org.ent.radiostation.<canonical_id>`

Annotators work on sampled search results and short paragraph-sized contexts, not complete long articles. The goal is to capture explicit mentions of canonical news agencies and radio stations cleanly while keeping the annotation task fast and consistent.

## Table Of Contents

- [Core Task](#core-task)
- [Annotation Unit](#annotation-unit)
- [Entity Families](#entity-families)
  - [News Agencies](#news-agencies)
  - [Radio Stations](#radio-stations)
- [Positive And Negative Decisions](#positive-and-negative-decisions)
  - [Annotate](#annotate)
  - [Do Not Annotate](#do-not-annotate)
- [Boundaries](#boundaries)
- [OCR And Identifiability](#ocr-and-identifiability)
- [Labels And Exclusions](#labels-and-exclusions)
- [Paragraph-Level Sampling Workflow](#paragraph-level-sampling-workflow)
- [Quality Statuses](#quality-statuses)
- [Differences From The MA Thesis Guidelines](#differences-from-the-ma-thesis-guidelines)
- [Examples](#examples)

## Core Task

Annotate the visible organization-name span for every explicit mention of a specific canonical news agency. For radio stations and broadcasters, annotate the visible organization-name span when the mention refers to the broadcaster/media outlet, its broadcasts, programmes, institutional organization, media staff, or media-source function.

Typical positive examples:

- `Reuters meldet ...` -> annotate `Reuters`
- `Selon l'agence Havas ...` -> annotate `agence Havas`
- `D.N.B. berichtet ...` -> annotate `D.N.B.`
- `Radio Londres annonce ...` -> annotate `Radio Londres`
- `Nach einer Meldung der BBC ...` -> annotate `BBC`
- `Le poste de Moscou diffuse ...` -> annotate the mapped station expression if canonical metadata supports it
- an article about Reuters, BBC, or another canonical organization as a topic
- a business story about an agency merger, office, ownership, staff, or infrastructure
- a programme schedule, channel listing, or broadcast listing that mentions a canonical radio station
- a broadcaster-related programme item such as `BBC Orchestra`, `BBC Scottish Orchestra`, or a BBC broadcast service

Typical negative contexts:

- a generic phrase such as `une agence`, `ag.`, or `Agentur` without a resolved real organization
- an author signature or correspondent attribution
- a homographic non-media organization, club, or team such as `BBC (Damen)` in a basketball fixture list

The annotation target is the organization mention, not the whole sentence and not the article.

## Annotation Unit

The new workflow annotates short contexts sampled from search results:

- Prefer one paragraph or a compact paragraph window around the search hit.
- Include enough surrounding text to identify the organization and its boundaries.
- Do not require the full article unless the short context is ambiguous.
- If the search hit is in a title or dateline, include the following paragraph when possible.
- If a paragraph contains multiple specific canonical organization mentions, annotate all accepted mentions in that paragraph.
- If the paragraph contains no accepted organization mention, keep it as a negative example when it is useful for disambiguation.

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
- Agence Radio

Only labels backed by canonical metadata in `resources/newsagency_seeds.json` are trainable labels.

### Radio Stations

Use `org.ent.radiostation.<canonical_id>` for real radio stations or broadcasters when the mention is tied to the organization's media, broadcasting, programme, news, or institutional broadcaster function.

Examples:

- BBC
- Radio Londres
- Radio Paris
- Radio Moscou / Radio Moscow
- Radio Bucarest / Radio Bucharest
- Voice of America
- Radio Free Europe
- Deutsche Welle
- RTS / Radio Télévision Suisse / Radio Suisse Romande / RSR
- RTL / Radio Luxembourg / Radio Télévision Luxembourg

Annotate specific canonical radio-station mentions when the context is connected to broadcasting, media production, media organizations, programme schedules, news/source attribution, or institutional broadcaster activity.

Treat broad broadcasters such as the BBC as media outlets/broadcasters for this dataset, even when the visible service is television rather than radio. `BBC Television`, `BBC TV`, and television-programme contexts are positive when they refer to the broadcaster/media outlet.

Use the publication date and surrounding programme/source context to disambiguate BBC-related London radio names. For World War II and occupation-era material, normalize popular foreign-language names for BBC broadcasts from London to `org.ent.radiostation.bbc`. This includes `Radio Londres`, `Radio London`, `Radio Londra`, and `Londoner Rundfunk` when the context is a broadcast, source attribution, programme, or broadcaster mention. These names were often listener/newspaper labels for BBC foreign-language services rather than separate station names. The broadcast content may involve Free French, exile-government, resistance, or allied contributors, but for this dataset the media outlet label is still BBC.

For earlier programme guides, especially 1920s material, `Radio-Londres` may identify the London broadcasting station by city rather than the later wartime French-language service. A wavelength such as `365 m` is a strong contextual clue for the London station 2LO/BBC London transmitter. Annotate the visible span as printed, for example `Radio-Londres`, and use `org.ent.radiostation.bbc` as the current canonical label. In notes or downstream entity-linking metadata this can be distinguished as a pre-war London station/BBC-related service, but do not create a separate training label unless the canonical metadata is explicitly extended.

Use `org.ent.radiostation.radio-bucharest` for `Radio Bucarest`, `Radio-Bucarest`, or `Radio Bucharest` when the context presents broadcasts or announcements from Bucharest as a media source. A sentence such as `Radio-Bucarest annonce ...` is positive. In 1948 newspaper material this is compatible with Romanian foreign-language broadcasts from Bucharest, the service later known as Radio Romania International.

For radio-station names and acronyms, do not annotate every string match. If the same acronym/name is used for a sports club, local association, team, or other non-media organization, keep it negative/O.

## Positive And Negative Decisions

### Annotate

Annotate the visible organization-name span for every explicit mention of a specific canonical news agency. This is intentionally broader than the MA-thesis source-attribution setup: source attribution is not required. A mention remains positive when the article discusses the agency, its staff, directors, correspondents, offices, ownership, legal status, mergers, infrastructure, or role in public life.

For radio stations and broadcasters, annotate the visible organization-name span when the mention refers to the broadcaster/media outlet, its broadcasts, programmes, institutional organization, media staff, or media-source function.

Surrounding verbs and nouns are only context evidence. Do not annotate words such as `meldet`, `berichtet`, `annonce`, `dépêche`, `communiqué`, `émission`, or `broadcast` unless they are part of the visible organization name. In `Reuters meldet ...`, annotate only `Reuters`. In `Radio Londres annonce ...`, annotate only `Radio Londres`.

Common positive evidence includes:

- source formulas: `(Reuter)`, `(Havas)`, `(D.N.B.)`, `(A. T. S.)`, `Radio Londres:`
- indirect source attribution: `nach Reuter`, `selon Havas`, `d'après la BBC`
- source verbs near the mention: `meldet`, `berichtet`, `annonce`, `communique`, `déclare`, `diffuse`, `broadcasts`, `reports`
- source nouns near the mention: `Meldung`, `dépêche`, `communiqué`, `bulletin`, `émission`, `broadcast`

Also annotate institutional, business, and programme contexts:

- `Reuters eröffnet ein Büro ...`
- `La BBC emploie ...`
- `L'agence Havas fut critiquée ...`
- `Fusion de l'agence Havas avec ...`
- `Programme de Radio Londres ...`
- `BBC Orchestra ...`

Do not annotate the string when the context clearly refers to a different, derived, or homographic non-media organization rather than the canonical agency/broadcaster. For example, a sports fixture `BBC (Damen) — Nilvange (Damen)` is negative because `BBC` denotes a basketball/club/team context, not the broadcaster. The same principle applies to football clubs, local associations, teams, or other organizations that share an acronym or name with a media source.

### Agence Radio vs Radio Stations

`Agence Radio` is a historical French press agency, not a radio-station label. Despite the name, it distributed telegrams, international news, and political information to newspapers; `Radio` refers to radiotelegraph/wireless transmission technology and to the agency name, not to a broadcaster in ordinary source formulas.

Annotate formulaic dispatch-source mentions such as `(Radio.)` as `org.ent.pressagency.agence-radio` when the publication date and context support a French news-agency attribution. Strong positive clues include:

- French newspaper source formulas parallel to `(Havas.)`, `(Reuter.)`, `(D.N.B.)`, or `(A.F.P.)`
- dateline plus source pattern such as `Londres, le 15 janvier ... (Radio.)`
- dates in the agency's active period, especially 1918-1944
- political, diplomatic, financial, or international news dispatches rather than programme listings

Do not annotate bare `Radio` as Agence Radio when it is just a medium, a generic radio reference, a programme heading, or part of a canonical broadcaster/station name such as `Radio Paris`, `Radio Londres`, `Radio Moscou`, `Radio Vatican`, or `Radio Luxembourg`.

### Do Not Annotate

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

Annotate the shortest span that preserves the full visible organization-name surface. In compounds, the full compound token or hyphenated compound may be the correct practical span when a canonical agency name is embedded in it.

Include:

- abbreviation periods, including the final period of dotted acronyms: `D.N.B.`, `A.F.P.`
- abbreviation-internal hyphens or slashes when part of the name: `ATS-SDA`, `Kipa/Apic`
- words that are part of the official name: `Agence France Presse`, `United Press`
- generic type words when they are used as part of the proper-name surface: `Agence Havas`, `Agence Wolff`, `Agence Reuter`
- OCR-noisy characters that belong to the mention if the mention is still identifiable
- full compound tokens or hyphenated compounds when a canonical agency name is embedded in the compound

Exclude:

- sentence-final periods after an undotted name or plain acronym: annotate `Havas`, not `Havas.`, and `AFP`, not `AFP.`
- surrounding parentheses, brackets, quotation marks, commas, dashes, or colons
- generic words unless they are part of the proper name
- article titles or sentence context outside the name

Punctuation belongs inside the span when it is part of the visible agency abbreviation or name. This remains true at the end of a sentence. In `(A. F. P.).`, annotate `A. F. P.`: the period after `P` is part of the abbreviation, while the parentheses and the sentence period after the closing parenthesis stay outside. For undotted names or plain acronyms such as `Havas.` or `AFP.`, the final period is ordinary sentence punctuation and stays outside.

News-agency names with `Agence`:

- Include `Agence` when it immediately precedes a specific agency name and functions as part of the named mention.
- Exclude articles and elided articles before it: annotate `Agence Wolff`, not `l' Agence Wolff`.
- Prefer the full visible proper-name surface over the shortest canonical label token. For example, annotate `Agence Havas`, not only `Havas`, when both words are cleanly present.
- If the text only has the agency name without `Agence`, annotate the name alone: `Havas`, `Wolff`, `Reuter`, `Reuters`.
- If `agence` is lowercase or syntactically generic but immediately names the organization, include it when the phrase is still the proper-name surface: `l'agence Havas` -> `agence Havas`.
- Do not include generic descriptors that are not part of the name: in `une agence de presse Havas` or `l'agence télégraphique Reuter`, annotate `Havas` or `Reuter` unless the source clearly uses `Agence Havas` or `Agence Reuter` as the name.
- Do not include corrupted tokens merely because they might stand for `Agence`. If OCR gives `A qgcncc Reuter`, annotate the clean identifiable name `Reuter` and add a correction note if useful.
- If `Agence` is readable but the following agency token is OCR-noisy and identifiable, include the readable `Agence` plus the noisy agency token.

Examples:

| Text                     | Annotate       | Do not annotate             |
| ------------------------ | -------------- | --------------------------- |
| `l' Agence Wolff`        | `Agence Wolff` | `l' Agence Wolff`, `Wolff`  |
| `Agence Havas`           | `Agence Havas` | `Havas`                     |
| `presse , Havas .`       | `Havas`        | `presse , Havas`, `Havas .` |
| `( A . F . P . ) .`      | `A . F . P .`  | `A . F . P`, `( A . F . P . )` |
| `l'agence Havas annonce` | `agence Havas` | `l'agence`, `Havas`         |
| `A qgcncc Reuter`        | `Reuter`       | `A qgcncc Reuter`           |

Compounds:

- If a canonical news-agency name appears inside a compound, annotate the full compound token or hyphenated compound.
- This rule is intended to keep annotation fast, reproducible, and compatible with token-level BIO export.
- The canonical label should still refer to the agency, even when the surface span contains a compound suffix or modifier.
- Use `review` only when the embedded agency name is not clearly identifiable or the compound could refer to something else.

Examples:

| Text                    | Annotate                | Label                         | Note                              |
| ----------------------- | ----------------------- | ----------------------------- | --------------------------------- |
| `Reutermeldung`         | `Reutermeldung`         | `org.ent.pressagency.reuters` | full compound token               |
| `Havasbericht`          | `Havasbericht`          | `org.ent.pressagency.havas`   | full compound token               |
| `DNB-Nachricht`         | `DNB-Nachricht`         | `org.ent.pressagency.dnb`     | hyphenated compound               |
| `Reuters-Korrespondent` | `Reuters-Korrespondent` | `org.ent.pressagency.reuters` | hyphenated compound               |
| `Reuterbureau`          | `Reuterbureau`          | `org.ent.pressagency.reuters` | compound with historical spelling |

Radio-station names:

- Include `Radio` when it is part of the station name: `Radio Paris`, `Radio Moscou`.
- For `BBC`, annotate the acronym alone unless the visible name/service phrase includes a broadcaster-service word such as `Television` or `TV`.
- Include `Television` in `BBC Television` when both words form the visible broadcaster-service name. Annotate `BBC` alone in generic phrases such as `BBC announced ...` or `on BBC`.
- Do not include words like `poste`, `sender`, or `station` when they are only generic descriptors.
- Include such words only when the expression functions as a historical station label and the station would otherwise be hard to identify.

Examples:

| Text                             | Annotate          | Label or decision                                 | Note                          |
| -------------------------------- | ----------------- | ------------------------------------------------- | ----------------------------- |
| `Radio Paris annonce ...`        | `Radio Paris`     | `org.ent.radiostation.radio_paris`                | `Radio` is part of the name   |
| `la station BBC annonce ...`     | `BBC`             | `org.ent.radiostation.bbc`                        | `station` is generic          |
| `le poste de Moscou diffuse ...` | `poste de Moscou` | review or canonical radio-station label if mapped | historical station expression |
| `Nach einer Sendung der BBC ...` | `BBC`             | `org.ent.radiostation.bbc`                        | source-like use               |

## OCR And Identifiability

Historical OCR is noisy. Annotate the visible OCR surface when a canonical media-source mention is reasonably identifiable from the surface and local context. Do not require or invent a corrected surface form during annotation; learning reasonable OCR variants is the model's responsibility.

Rules:

- Annotate noisy but identifiable mentions.
- Do not create a new label for an OCR variant.
- If OCR noise makes the organization impossible to identify, do not assign a canonical label.
- If the mention boundary is uncertain but the organization is clear, select the best surface span and flag the row for review.

Examples:

- `Reutei` may be annotated as Reuters when local context makes it reasonably identifiable.
- `D . N . B .` remains the visible span when it is the OCR/tokenized form of `D.N.B.`.
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
4. Annotate accepted organization mentions in that paragraph.
5. Mark hard negatives where the alias appears but is not a specific canonical organization mention.
6. Record the decision status, query provenance, and metadata.
7. Run an alias-based missed-mention audit over the paragraph before export.

Keep negative examples. They are especially important for short acronyms and radio-station names:

- `AP` as a non-agency acronym
- `ATP`, `FN`, or sports abbreviations
- BBC as a non-broadcaster acronym or unrelated OCR/string match
- generic radio schedule words without a specific canonical station
- generic `ag.`, `agence`, `Agentur`

## Quality Statuses

Each paragraph candidate should receive a curation status:

| Status       | Meaning                                                      | Training use            |
| ------------ | ------------------------------------------------------------ | ----------------------- |
| `accepted`   | Contains one or more verified canonical agency/station mentions. | Include.                |
| `negative`   | Contains no specific canonical agency/station mention but is useful contrastive material. | Include as all-`O`.     |
| `review`     | Potential mention needs a decision or canonical metadata update. | Exclude until resolved. |
| `non_usable` | Too noisy, too little context, wrong language, or broken OCR. | Exclude.                |

Use `review` for ambiguous historical labels rather than forcing uncertain annotations.

## Differences From The MA Thesis Guidelines

The new guidelines change the central semantic rule from the MA thesis. The MA thesis focused on explicit source attributions. The new dataset annotates every explicit mention of a specific canonical news agency in the paragraph, and radio-station/broadcaster mentions when they are tied to the organization's media function.

Important continuities:

- OCR-noisy but identifiable mentions should be retained as visible OCR spans.
- Periods that are part of an agency abbreviation or visible name remain part of the mention, even sentence-finally.
- Generic words like `agence` or `Agentur` are excluded unless part of a proper name.
- Compounds containing recognizable canonical agency names should be annotated as full compound tokens or hyphenated compounds.
- Author attributions are not target entities.

Important changes:

- The new dataset includes both news agencies and radio stations in one model.
- Source attribution is no longer required for a positive label.
- Mentions of news agencies as article topics, institutional actors, business entities, offices, staff, infrastructure, or source attributions are positive when the organization is specific and canonical.
- Radio stations and broadcasters are first-class labels when the mention is tied to broadcasting, media production, media-source use, programme schedules, news/source attribution, or institutional broadcaster activity.
- Radio-station acronyms used for unrelated clubs, teams, or associations are negative/O.
- Annotation is paragraph-centered, not full-document-centered.
- The workflow begins from sampled search results and query provenance.
- Negative paragraph examples are deliberately curated for disambiguation.
- `unk` is no longer a trainable label.
- Bare `ag` is no longer a trainable news-agency label.
- `pers.ind.articleauthor` is excluded rather than modeled as a disambiguation tag.
- The primary data format is Hugging Face-style JSONL, not HIPE TSV.
- Entity spans must support both token-level BIO labels and character offsets in paragraph text.

The practical consequence is that annotators should spend less time deciding whether a mention is a source attribution and more time making precise paragraph-level mention, boundary, and canonical-label decisions.

## Examples

| Text                                         | Decision                                             | Span              | Label                                                        |
| -------------------------------------------- | ---------------------------------------------------- | ----------------- | ------------------------------------------------------------ |
| `Selon Reuters, la situation reste confuse.` | annotate                                             | `Reuters`         | `org.ent.pressagency.reuters`                                |
| `Reuters ouvre un nouveau bureau.`           | annotate                                             | `Reuters`         | `org.ent.pressagency.reuters`                                |
| `D.N.B. meldet aus Berlin ...`               | annotate                                             | `D.N.B.`          | `org.ent.pressagency.dnb`                                    |
| `l'agence Havas annonce ...`                 | annotate                                             | `agence Havas`    | `org.ent.pressagency.havas`                                  |
| `Reutermeldung aus Berlin ...`               | annotate                                             | `Reutermeldung`   | `org.ent.pressagency.reuters`                                |
| `DNB-Nachricht über die Lage ...`            | annotate                                             | `DNB-Nachricht`   | `org.ent.pressagency.dnb`                                    |
| `Londres, le 15 janvier ... (Radio.)`        | annotate                                             | `Radio`           | `org.ent.pressagency.agence-radio`; dispatch-source formula  |
| `Nach einer Sendung der BBC ...`             | annotate                                             | `BBC`             | `org.ent.radiostation.bbc`                                   |
| `La BBC modifie son programme.`              | annotate                                             | `BBC`             | `org.ent.radiostation.bbc`                                   |
| `Radio Londres annonce ...`                  | annotate                                             | `Radio Londres`   | `org.ent.radiostation.bbc`                                   |
| `Radio Londra comunica ...`                  | annotate                                             | `Radio Londra`    | `org.ent.radiostation.bbc`                                   |
| `Londoner Rundfunk meldet ...`               | annotate                                             | `Londoner Rundfunk` | `org.ent.radiostation.bbc`                                 |
| `BBC Television diffuse ...`                 | annotate                                             | `BBC Television`  | `org.ent.radiostation.bbc`                                   |
| `un programme de BBC TV ...`                 | annotate                                             | `BBC TV`          | `org.ent.radiostation.bbc`                                   |
| `BBC Scottish Orchestra ...`                 | annotate                                             | `BBC`             | `org.ent.radiostation.bbc`                                   |
| `BBC (Damen) — Nilvange (Damen)`             | do not annotate                                      | none              | all `O`; basketball/team context, not broadcaster function   |
| `la radio diffuse le concert ...`            | do not annotate                                      | none              | generic medium, not Agence Radio                            |
| `Radio Paris annonce ...`                    | annotate                                             | `Radio Paris`     | `org.ent.radiostation.radio_paris`                           |
| `la station BBC annonce ...`                 | annotate                                             | `BBC`             | `org.ent.radiostation.bbc`                                   |
| `le poste de Moscou diffuse ...`             | review or annotate if canonical mapping is available | `poste de Moscou` | `org.ent.radiostation.<canonical_id>` or review              |
| `Reutei annonce ...`                         | annotate if identifiable                             | `Reutei`          | `org.ent.pressagency.reuters`; visible OCR span              |
| `D . N . B . meldet ...`                     | annotate if offsets are preserved                    | `D . N . B .`     | `org.ent.pressagency.dnb`; visible dotted abbreviation       |
| `AP bat son record ...`                      | do not annotate or mark review                       | none              | all `O`, unless context clearly means Associated Press       |
| `(AP) Washington ...`                        | annotate if source context is clear                  | `AP`              | `org.ent.pressagency.ap`                                     |
| `ag. meldet ...`                             | do not label as agency                               | none              | all `O`, possible review                                     |
| `sn` as a signature                          | do not annotate                                      | none              | all `O`                                                      |
