# Label Policy

Annotator-facing rules live in [../docs/annotation_guidelines.md](../docs/annotation_guidelines.md). This file is the short machine-policy summary for label generation, curation checks, and exclusions.

Policy version: 2.0.

## Scope

The model predicts explicit mentions of canonical media-source organizations in paragraph-sized historical newspaper contexts:

- `org.ent.pressagency.<canonical_id>` for real news agencies and press agencies.
- `org.ent.radiostation.<canonical_id>` for real radio stations and broadcasters.

Annotate every explicit mention of a specific canonical news agency. For radio stations and broadcasters, annotate mentions when the context relates to the organization's media, broadcast, programme, news, publication, institutional broadcaster, or media-source function.

Source attribution is not required for a positive label.

## Trainable Labels

Trainable labels must be backed by canonical metadata:

- news agencies: `resources/newsagency_seeds.json`
- radio stations: `resources/radiostation_seeds.json`

Do not create trainable labels from raw aliases, OCR variants, unresolved unknowns, or generic source markers. If a real organization is missing from metadata, mark the candidate for review and add canonical metadata before export.

## Exclusions

These are not trainable output labels:

- `unk`
- `org.ent.pressagency.unk`
- unresolved bare `ag`
- `org.ent.pressagency.ag`
- `pers.ind.articleauthor`
- generic organization labels
- generic source markers without a resolved organization
- homographic radio-station acronyms used for unrelated non-media clubs, teams, or associations

Bare `ag` in the thesis meant generic `ag.`, `agence`, or `Agentur`. It remains negative/O unless a specific canonical organization can be resolved.

Do not annotate:

- generic phrases such as `une agence`, `ag.`, `Agentur`, `bureau`, or `correspondance` without a resolved real organization
- author or correspondent signatures such as initials, reporter names, or old `pers.ind.articleauthor` cases
- OCR strings where the organization cannot be identified confidently

## Positive Contexts

Positive mentions include:

- source formulas: `(Reuter)`, `(Havas)`, `(D.N.B.)`, `Radio Londres:`
- indirect source attribution: `nach Reuter`, `selon Havas`, `d'après la BBC`
- institutional or business mentions: offices, mergers, ownership, staff, infrastructure
- article-topic mentions about a canonical news agency, or about a radio station/broadcaster in its media role
- programme schedules, channel listings, and broadcast listings naming a canonical radio station
- broadcaster-related programme entities such as `BBC Orchestra` or `BBC Scottish Orchestra`

Radio-station acronym/name matches are negative when the context clearly refers to a non-media organization, for example a sports fixture listing such as `BBC (Damen) — Nilvange (Damen)`.

## Boundary Policy

Annotate the shortest span that preserves the full visible organization-name surface.

Include:

- abbreviation-internal periods: `D.N.B.`, `A.F.P.`
- abbreviation-internal hyphens or slashes when part of the name: `ATS-SDA`, `Kipa/Apic`
- words that are part of the official or visible name: `Agence France Presse`, `United Press`
- generic type words when used as part of the proper-name surface: `Agence Havas`, `Agence Wolff`, `Agence Reuter`
- full compound tokens or hyphenated compounds when a canonical agency name is embedded in the compound
- OCR-noisy characters that belong to an identifiable mention

Exclude:

- sentence-final periods after a name: `Havas`, not `Havas.`
- surrounding parentheses, brackets, quotation marks, commas, dashes, or colons
- articles and elided articles before a name: `Agence Wolff`, not `l' Agence Wolff`
- generic words unless they are part of the proper name
- article titles or sentence context outside the name

## `Agence` Boundary Rule

Use one deterministic rule for agency names with `Agence`:

- Include `Agence` when it immediately precedes a specific agency name and functions as part of the named mention.
- Prefer `Agence Havas`, `Agence Wolff`, or `Agence Reuter` over only `Havas`, `Wolff`, or `Reuter` when both words are cleanly present.
- If the text only has the agency name without `Agence`, annotate the name alone.
- If lowercase `agence` immediately names the organization, include it when the phrase is still the proper-name surface: `l'agence Havas` -> `agence Havas`.
- Do not include generic descriptors in phrases such as `une agence de presse Havas` or `l'agence télégraphique Reuter`; annotate `Havas` or `Reuter` unless the source clearly uses `Agence Havas` or `Agence Reuter` as the name.
- Do not include corrupted tokens merely because they might stand for `Agence`: `A qgcncc Reuter` -> `Reuter`.

## Compounds

If a canonical news-agency name appears inside a compound, annotate the full compound token or hyphenated compound and keep the canonical agency label.

Examples:

- `Reutermeldung` -> `org.ent.pressagency.reuters`
- `Havasbericht` -> `org.ent.pressagency.havas`
- `DNB-Nachricht` -> `org.ent.pressagency.dnb`
- `Reuters-Korrespondent` -> `org.ent.pressagency.reuters`

Use review only when the embedded agency name is not clearly identifiable or the compound may refer to something else.

## Radio Stations

Annotate specific canonical radio-station mentions when the context is connected to broadcasting, media production, media organizations, programme schedules, news/source attribution, or institutional broadcaster activity.

Treat broad broadcasters such as the BBC as media outlets/broadcasters for this dataset, even when the visible service is television rather than radio. `BBC Television`, `BBC TV`, and television-programme contexts are positive when they refer to the broadcaster/media outlet.

Use publication date and context to disambiguate BBC-related London radio names. Normalize wartime foreign-language names for BBC broadcasts from London to `org.ent.radiostation.bbc` when the context is a broadcast, source attribution, programme, or broadcaster mention. This includes `Radio Londres`, `Radio London`, `Radio Londra`, and `Londoner Rundfunk`. These forms are treated as BBC service names/listener labels in occupied-Europe contexts, not as separate trainable station labels.

For pre-war programme guides, especially 1920s material, `Radio-Londres` may refer to the London broadcasting station by city name, for example the 2LO/BBC London transmitter. Wavelengths around `365 m` support that reading. Keep the observed span (`Radio-Londres`) and use `org.ent.radiostation.bbc` as the current canonical training label unless a separate canonical station label is explicitly added later.

Do not annotate the same acronym/name when it denotes an unrelated sports club, local association, team, or other non-media organization.

Boundary rules:

- Include `Radio` when it is part of the station name: `Radio Paris`, `Radio Moscou`.
- For `BBC`, annotate the acronym alone unless the visible name/service phrase includes a broadcaster-service word such as `Television` or `TV`.
- Include `Television` in `BBC Television` when both words form the visible broadcaster-service name. Annotate `BBC` alone in generic phrases such as `BBC announced ...` or `on BBC`.
- Exclude generic descriptors such as `poste`, `sender`, or `station` unless the expression functions as a historical station label and is mapped in canonical metadata.

## Agence Radio

`Agence Radio` (`org.ent.pressagency.agence-radio`) is a press-agency label, not a radio-station label. Use it for formulaic source attributions such as `(Radio.)` only when publication date and context support the historical French news agency, especially 1918-1944 French dispatch contexts parallel to `(Havas.)` or `(Reuter.)`.

Do not use `org.ent.pressagency.agence-radio` for generic radio medium references or for broadcaster/station names such as `Radio Paris`, `Radio Londres`, `Radio Moscou`, `Radio Vatican`, or `Radio Luxembourg`.

## OCR And Normalization

Keep the observed surface form in offsets and spans. Store normalized/corrected surfaces in metadata when available.

Rules:

- Annotate noisy but identifiable mentions.
- Do not create a new label for an OCR variant.
- If OCR noise makes the organization impossible to identify, keep the row negative/O or mark it for review.
- If the boundary is uncertain but the organization is clear, choose the best visible span and record a correction note.

## Curation Statuses

Paragraph candidates use these statuses:

- `accepted`: one or more verified canonical agency/station mentions; include in training.
- `negative`: no specific canonical mention, but useful contrastive material; include as all-`O`.
- `review`: potential mention needs a decision or canonical metadata update; exclude until resolved.
- `non_usable`: too noisy, too little context, wrong language, or broken OCR; exclude.
