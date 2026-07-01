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
  - [Commercial And Administrative Uses In Advertisements](#commercial-and-administrative-uses-in-advertisements)
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
- a press-agency name used only as an advertising, reply-address, box-number, classified, or commercial intermediary
- a homographic non-media organization, club, or team such as `BBC (Damen)` in a basketball fixture list
- a stock-market or securities-price listing where a media-company name such as `Reuters` appears only as a traded company/security among other quoted stocks

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
- Tanjug / Tan Jug.
- Telegraphen-Union / T.U. / contextual `(UTA)`
- CTK / ČTK / tschechoslowakische Nachrichtenagentur
- ATA / Albanian Telegraphic Agency / albanische Nachrichtenagentur ATA
- Russische Telegraphen-Agentur / St. Petersburg Telegraph Agency
- Wolff
- Agence Radio

Only labels backed by canonical metadata in `resources/newsagency_seeds.json` are trainable labels.

Use `org.ent.pressagency.telegraphen-union` for `Telegraphen-Union`, `T.U.`, and contextual Weimar-period source formulas such as `Berlin, 7. Januar. (UTA)`. For `UTA`, require source-formula context; do not treat arbitrary `UTA` in running text as a press-agency mention, and do not map it to `org.ent.pressagency.ats-sda`.

Use `org.ent.pressagency.wolff` for the Wolff/Continental agency complex: `Wolff`, `W.T.B.`, `Wolffs Telegraphisches Bureau`, `Continental-Telegraphen-Compagnie`, `Continental Telegraph Company`, `The Continental`, `Agence Continentale`, and `Compagnie télégraphique continentale`. The Continental company was the corporate frame behind the operating agency commonly cited as Wolff, so this inventory does not assign it a separate trainable entity. Also normalize explicit `Conti-Nachrichtendienst` mentions to Wolff.

Treat bare `Conti` as a contextual alias only. Annotate it as `org.ent.pressagency.wolff` in a clear parenthesized or formulaic dispatch attribution, for example `Berlin. 25. Febr. (Conti.)`. Do not annotate arbitrary `Conti` in running text: it may be a surname, an unrelated abbreviation, or another corporate reference. The source-formula restriction applies to bare `Conti`, not to an explicit full Continental company or `Conti-Nachrichtendienst` name.

In source phrases such as `Telegraphen-Union berichtet:`, annotate only `Telegraphen-Union` with `org.ent.pressagency.telegraphen-union`. The following verb (`berichtet`) is context evidence and must stay outside the entity span, even if a model predicts it as another agency.

Use `org.ent.pressagency.ctk` for CTK/ČTK, Ceteka, the Czech/Czechoslovak News Agency, `Československá tisková kancelář`, `tschechoslowakische Nachrichtenagentur`, `tschechoslowakischen Nachrichtenagentur`, `Tschechoslowakisches Nachrichtenbüro`, and comparable language-specific renderings of the Czechoslovak/Czech press agency. In phrases such as `Meldung der tschechoslowakischen Nachrichtenagentur`, annotate only the visible agency phrase (`tschechoslowakischen Nachrichtenagentur`) and exclude surrounding evidence words such as `Meldung der`.

Use `org.ent.pressagency.ata` for ATA/ATSH, the Albanian Telegraphic Agency, `Agjencia Telegrafike Shqiptare`, `albanische Nachrichtenagentur`, `Agence télégraphique albanaise`, and comparable language-specific renderings of the Albanian national news agency. In phrases such as `Die albanische Nachrichtenagentur ATA bestätigte ...`, prefer the full visible agency-name phrase (`albanische Nachrichtenagentur ATA`) when cleanly present. Annotate `ATA` alone when only the acronym is present or when the descriptive phrase is outside the selected span.

Use `org.ent.pressagency.st-petersburg-telegraph-agency` for the Russian imperial St. Petersburg/Petrograd Telegraph Agency and German historical renderings such as `Russische Telegraphen-Agentur`, `Russische Telegrafen-Agentur`, or `Petersburger Telegraphen-Agentur`. In 1904-1918 contexts, do not automatically normalize these predecessor mentions to `org.ent.pressagency.tass`. Preserve the visible OCR surface in the span, for example `Russische Teleglllvhen-Agentur`, but assign the St. Petersburg Telegraph Agency label when the organization is identifiable.

Use `org.ent.pressagency.tass` only for mentions that name TASS/Tass, ITAR-TASS, Russian News Agency TASS, or the Soviet Telegraph Agency of the Soviet Union. Earlier Russian imperial/Petersburg agency mentions and ROSTA are predecessor organizations and require their own canonical metadata rather than silent TASS normalization.

Use `org.ent.pressagency.apa` for the Austrian Press Agency, including `APA`, lowercase `apa` in clear Austrian source formulas, `Austria Presse-Agentur`, and comparable renderings. Do not normalize Austrian `apa` to Associated Press (`org.ent.pressagency.ap`) merely because the surface is short or lowercase.

Use `org.ent.pressagency.ddp-dapd` for `DDP`, `ddp`, `DAPD`, `Deutscher Depeschendienst`, and clear source or institutional mentions of the German agency. In compounds such as `ddp-Gespräch`, annotate the full compound token when the embedded agency is clearly identifiable.

Use `org.ent.pressagency.palach-press` only for the agency `Palach Press`. Do not annotate references to the person Jan Palach, including `Jan Palach`, `Jan Palachs`, or text about his suicide, funeral, grave, memorial, or political symbolism.

Short aliases such as `PTA` or `SPTA` for `org.ent.pressagency.st-petersburg-telegraph-agency` require clear press-agency or source-formula context. Do not annotate arbitrary `PTA` hits in sports tables, point scores, prices, advertisements, or OCR fragments such as `CA PTA IN` for `CAPTAIN`.

### Radio Stations

Use `org.ent.radiostation.<canonical_id>` for real radio stations or broadcasters when the mention is tied to the organization's media, broadcasting, programme, news, or institutional broadcaster function.

Examples:

- BBC
- Radio Londres
- Radio Paris
- Radio Moscou / Radio Moscow
- Radio Bucarest / Radio Bucharest
- Vatican Radio / Radio Vatican / Radio Vatikan
- Voice of America
- Radio Free Europe / Radio Europe libre / Radio Freies Europa
- Deutsche Welle
- RTS / Radio Télévision Suisse / Radio Suisse Romande / RSR
- RTL / Radio Luxembourg / Radio Télévision Luxembourg

Annotate specific canonical radio-station mentions when the context is connected to broadcasting, media production, media organizations, programme schedules, news/source attribution, or institutional broadcaster activity.

Treat broad broadcasters such as the BBC as media outlets/broadcasters for this dataset, even when the visible service is television rather than radio. `BBC Television`, `BBC TV`, and television-programme contexts are positive when they refer to the broadcaster/media outlet.

Use the publication date and surrounding programme/source context to disambiguate BBC-related London radio names. For World War II and occupation-era material, normalize popular foreign-language names for BBC broadcasts from London to `org.ent.radiostation.bbc`. This includes `Radio Londres`, `Radio London`, `Radio Londra`, and `Londoner Rundfunk` when the context is a broadcast, source attribution, programme, or broadcaster mention. These names were often listener/newspaper labels for BBC foreign-language services rather than separate station names. The broadcast content may involve Free French, exile-government, resistance, or allied contributors, but for this dataset the media outlet label is still BBC.

For earlier programme guides, especially 1920s material, `Radio-Londres` may identify the London broadcasting station by city rather than the later wartime French-language service. A wavelength such as `365 m` is a strong contextual clue for the London station 2LO/BBC London transmitter. Annotate the visible span as printed, for example `Radio-Londres`, and use `org.ent.radiostation.bbc` as the current canonical label. In notes or downstream entity-linking metadata this can be distinguished as a pre-war London station/BBC-related service, but do not create a separate training label unless the canonical metadata is explicitly extended.

Use `org.ent.radiostation.radio-bucharest` for `Radio Bucarest`, `Radio-Bucarest`, or `Radio Bucharest` when the context presents broadcasts or announcements from Bucharest as a media source. A sentence such as `Radio-Bucarest annonce ...` is positive. In 1948 newspaper material this is compatible with Romanian foreign-language broadcasts from Bucharest, the service later known as Radio Romania International.

Use `org.ent.radiostation.vatican-radio` for `Vatican Radio`, `Radio Vatican`, `Radio-Vatican`, `Radio Vatikan`, `Radio Vaticano`, or `Radio Vaticana` when the context refers to the broadcaster, a broadcast, a programme, or a source attribution. Descriptive forms such as `radio vaticane` and `radio de la Cité du Vatican` are also positive when the phrase refers to the broadcaster. Example: `Nach einer Meldung von Radio Vatican ...` is positive. In `la radio de la Cité du Vatican a diffusé ...`, annotate `radio de la Cité du Vatican` and exclude the article `la`.

Use `org.ent.radiostation.deutsche-welle` for the modern Deutsche Welle broadcaster and for historical 1920s/1930s programme-list references to Deutsche Welle GmbH/Deutschlandsender. In forms such as `Deutsche Welle-Königswusterhausen`, include the attached hyphenated station-location suffix because it is part of the visible station listing.

For radio-station names and acronyms, do not annotate every string match. If the same acronym/name is used for a sports club, local association, team, or other non-media organization, keep it negative/O.

When a radio-station mention is coordinated with another broadcaster by a slash or conjunction, annotate only the part that names the canonical broadcaster. For example, in `Deutsche Welle/Deutschlandfunk`, annotate `Deutsche Welle` only unless `Deutschlandfunk` is also backed by canonical metadata.

Use `org.ent.radiostation.radio-liberty` for `Radio Liberty`, `Radio Liberation`, and `Radio Libération` when the context refers to the broadcaster or its broadcasts.

Use `org.ent.radiostation.polskie-radio` for `Polskie Radio` and for historical foreign-language references to Polish radio such as `Radio Varsovie`, `Radio Warschau`, or `Radio Warsaw` when the context presents broadcasts or announcements from Warsaw/Poland as a media source.

Use `org.ent.radiostation.voice-of-america` for `Voice of America`, `Voix de l'Amérique`, `Stimme Amerikas`, and comparable language-specific renderings when the phrase refers to the broadcaster, a broadcast, or a programme/source attribution.

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

Do not annotate stock-market quotation tables, securities listings, or share-price reports when the string names a listed company/security rather than a media-source mention. For example, in a list such as `Prudential ... Rank Org ... Reed ... Reuters 15.2 ... Shell Transp ... Unilever ...`, `Reuters` is a stock/security entry and should remain `O`, even though the underlying company is historically connected to the news agency. This exclusion applies to comparable quoted-company contexts for any media-source organization.

### Commercial And Administrative Uses In Advertisements

Do not annotate a press-agency name when it appears solely in a customer-facing commercial or administrative role unrelated to news production. This includes:

- a reply or box-number intermediary in a classified advertisement;
- an advertising-placement or correspondence address;
- contact instructions in employment, property, travel, or other advertisements;
- formulas such as `apply to`, `reply to`, `under No.`, or `send correspondence to` followed by an agency office.

The organization's historical identity as a press agency is not sufficient in these cases. The local context must present it as a news source, news distributor, journalistic organization, or media institution. Keep the name `O` when it merely tells readers where to apply, reply, or send correspondence.

This exclusion does not change the rule for genuine institutional or business reporting. A news article about Havas opening an office, employing staff, changing ownership, or merging with another organization remains positive because Havas is being discussed as an institution. The exclusion applies when the name serves only as part of an advertisement's transactional contact instructions.

Examples:

- `Apply Agence Havas Monte-Carlo No 1174.` -> do not annotate; commercial advertisement contact.
- `Reply in confidence under No L. 39, Agence Havas, Brussels.` -> do not annotate; reply/box-number intermediary.
- `Selon l'Agence Havas, les négociations ont repris.` -> annotate `Agence Havas`; news-source attribution.
- `Une dépêche de l'Agence Havas annonce ...` -> annotate `Agence Havas`; news-distribution context.

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

Do not annotate hard-negative alias matches when the local context identifies a non-media meaning:

- `Jan Palach`, `Jan Palachs`, or memorial/funeral/grave contexts are person references, not `Palach Press`.
- `PTA` in sports scores, points tables, prices, or OCR-split `CAPTAIN` is not the St. Petersburg Telegraph Agency.
- short acronyms in football, basketball, clubs, local associations, advertisements, price lists, or job listings are negative unless the media-source organization is clearly identified.
- OCR fragments such as `dapder`, `DapceviC`, or broken strings that only accidentally resemble an alias should remain `O` unless the agency is identifiable from the surrounding context.

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

Co-occurring source formulas:

- If a source formula contains several specific canonical agencies, annotate all valid agency mentions in the formula.
- Exclude separators such as `/`, commas, parentheses, brackets, and dashes unless they are part of the abbreviation itself.
- When a full agency name and an acronym occur together, annotate both as separate spans if both are visible and tokenizable.
- Use the same canonical label for both mentions when they refer to the same organization.

Examples:

| Text | Annotate | Labels |
| ---- | -------- | ------ |
| `(sda / apa / dpa)` | `sda`, `apa`, `dpa` | `org.ent.pressagency.ats-sda`, `org.ent.pressagency.apa`, `org.ent.pressagency.dpa` |
| `Austria Presse-Agentur (APA)` | `Austria Presse-Agentur`, `APA` | `org.ent.pressagency.apa` |
| `Deutscher Depeschendienst (ddp)` | `Deutscher Depeschendienst`, `ddp` | `org.ent.pressagency.ddp-dapd` |

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
| `Radio Paris annonce ...`        | `Radio Paris`     | `org.ent.radiostation.radio-paris`                | `Radio` is part of the name   |
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
- Press-agency names used only as advertising contacts, reply-address intermediaries, or box-number handlers are negative/O; this does not exclude genuine institutional or business reporting about the agency.
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
| `Reed 7.125 7 Reuters 15.2 15.4 Shell Transp 6.61` | do not annotate                              | none              | all `O`; stock/security quotation table, not media-source mention |
| `Apply Agence Havas Monte-Carlo No 1174.`    | do not annotate                                      | none              | all `O`; commercial advertisement contact, not news-source use |
| `Reply under No L. 39, Agence Havas, Brussels.` | do not annotate                                   | none              | all `O`; reply/box-number intermediary in an advertisement   |
| `la radio diffuse le concert ...`            | do not annotate                                      | none              | generic medium, not Agence Radio                            |
| `Radio Paris annonce ...`                    | annotate                                             | `Radio Paris`     | `org.ent.radiostation.radio-paris`                           |
| `la station BBC annonce ...`                 | annotate                                             | `BBC`             | `org.ent.radiostation.bbc`                                   |
| `le poste de Moscou diffuse ...`             | review or annotate if canonical mapping is available | `poste de Moscou` | `org.ent.radiostation.<canonical_id>` or review              |
| `Reutei annonce ...`                         | annotate if identifiable                             | `Reutei`          | `org.ent.pressagency.reuters`; visible OCR span              |
| `D . N . B . meldet ...`                     | annotate if offsets are preserved                    | `D . N . B .`     | `org.ent.pressagency.dnb`; visible dotted abbreviation       |
| `AP bat son record ...`                      | do not annotate or mark review                       | none              | all `O`, unless context clearly means Associated Press       |
| `(AP) Washington ...`                        | annotate if source context is clear                  | `AP`              | `org.ent.pressagency.ap`                                     |
| `ag. meldet ...`                             | do not label as agency                               | none              | all `O`, possible review                                     |
| `sn` as a signature                          | do not annotate                                      | none              | all `O`                                                      |
| `(sda / apa / dpa)` | annotate | `sda`, `apa`, `dpa` | `org.ent.pressagency.ats-sda`, `org.ent.pressagency.apa`, `org.ent.pressagency.dpa` |
| `Austria Presse-Agentur (APA) meldete ...` | annotate | `Austria Presse-Agentur`, `APA` | `org.ent.pressagency.apa` |
| `dem Deutschen Depeschendienst (ddp)` | annotate | `Deutschen Depeschendienst`, `ddp` | `org.ent.pressagency.ddp-dapd` |
| `Agence Belga meldet ...` | annotate | `Agence Belga` | `org.ent.pressagency.belga` |
| `Jan Palach, der Student ...` | do not annotate | none | all `O`; person mention, not Palach Press |
| `RESULTS UP TO DATE. Pta Played. Won. Lost ...` | do not annotate | none | all `O`; sports table, not St. Petersburg Telegraph Agency |
| `CA PTA IN` | do not annotate | none | all `O`; OCR split of `CAPTAIN` |
| `Deutsche Welle/Deutschlandfunk` | annotate if canonical context is clear | `Deutsche Welle` | `org.ent.radiostation.deutsche-welle`; exclude slash and neighbouring broadcaster |
| `Radio Liberation` | annotate if broadcaster context is clear | `Radio Liberation` | `org.ent.radiostation.radio-liberty` |
| `Radio Warschau meldete ...` | annotate | `Radio Warschau` | `org.ent.radiostation.polskie-radio` |
| `Voix de l'Amérique annonce ...` | annotate | `Voix de l'Amérique` | `org.ent.radiostation.voice-of-america` |
