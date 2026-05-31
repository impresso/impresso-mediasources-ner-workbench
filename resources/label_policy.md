# Label Policy

Annotator-facing rules live in [../docs/annotation_guidelines.md](../docs/annotation_guidelines.md). This file is the short machine-policy summary for labels and exclusions.

## Scope

The model predicts cited media-source mentions in historical newspaper articles:

- `org.ent.pressagency.<canonical_id>` for news agencies.
- `org.ent.radiostation.<canonical_id>` for radio stations.

Annotate an entity only when it is presented as the source, sender, broadcaster, or cited origin of information. Do not annotate an entity merely because the article is about that organization.

## Exclusions

These are not trainable output labels:

- `unk`
- `org.ent.pressagency.unk`
- unresolved bare `ag`
- `pers.ind.articleauthor`
- generic organization labels

Bare `ag` in the thesis meant generic `ag.`, `agence`, or `Agentur`. It requires a separate explicit decision before it can become a trainable source-marker class.

## Boundaries

- Keep abbreviation-internal periods, such as `D.N.B.` or `ag.`.
- Exclude sentence-final periods after a name or acronym.
- Exclude generic words such as `agence` or `Agentur` unless they are part of the proper name.
- For German compounds, annotate only the agency-name part, for example `Reuter` in `Reutermeldung`.
- Preserve OCR-correction metadata for noisy but identifiable mentions.
- Mark articles that are too noisy to understand as `non_usable`.
