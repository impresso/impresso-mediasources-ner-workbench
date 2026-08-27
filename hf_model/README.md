---
license: mit
language:
- fr
- de
- lb
pipeline_tag: token-classification
tags:
- impresso
- historical-newspapers
- news-agencies
- radio-stations
- media-sources
---

# mmBERT Impresso Media Sources NER

Fine-tuned token-classification model for media-source mention recognition in historical Impresso newspaper text.

The v2.0.0 model predicts cited source mentions for:

- news agencies, labelled as `org.ent.pressagency.<canonical_id>`
- radio stations, labelled as `org.ent.radiostation.<canonical_id>`

The repository name uses "media sources" because the label space may later grow to cover other cited media-source families.

## Provenance

- Dataset: `impresso-project/impresso-mediaagencies-ner-dataset`
- Dataset revision: `v2.0.0`
- Dataset commit: `a7ac5dc1ec0dd92ae848dbccd258aa0361830da3`
- Training code commit: not recorded by this completed run
- Publication/workbench commit: `429a3767288abd16a43b2f7996453f73df350c7c`
- Model revision: `v2.0.0`
- Model commit: `9899ad960b9bc310ee51cd7ee658fd3882b6b140`
- Base model: `impresso-project/mmbert-multilingual-impresso-continued-mlm`
- Upstream base: `jhu-clsp/mmBERT-base`
- License: MIT

The model was trained from the pinned published Hugging Face dataset commit above. The selected checkpoint was chosen on validation performance, not on the held-out test set. The completed training run did not record a Git SHA in `training_start_report.json`; the publication/workbench commit is therefore recorded separately and should not be treated as the exact training-code commit.

## Training Setup

- Annotation tokenization: `unicode-word-punctuation-v1`
- Subtoken supervision: all subtokens labelled, with B-to-I conversion for continuation subtokens
- Decoder used for evaluation/deployment: `first_subtoken_viterbi`
- Adaptation: top 4 ModernBERT layers unfrozen

The model `config.json` records `annotation_tokenization`, `label_all_tokens`, `subtoken_labeling`, and `subtoken_decoding`. Inference must apply the declared annotation-token profile and the declared `subtoken_decoding` policy. `label_all_tokens` describes training supervision; it does not by itself define inference decoding.

## Evaluation

Exact entity metrics use the constrained `first_subtoken_viterbi` decoder over the checkpoint label space.

Validation metrics for the selected checkpoint:

- Precision: 0.9398
- Recall: 0.9174
- F1: 0.9285
- Correct/gold/predicted entities: 500 / 545 / 519

Held-out test metrics:

- Precision: 0.9346
- Recall: 0.8644
- F1: 0.8981
- Correct/gold/predicted entities: 529 / 612 / 566

Runtime inference validation:

- Release-artifact inference was verified on the complete v2.0.0 held-out test set.
- The Hugging Face runtime pipeline matched the evaluator's decoded BIO sequence for 458 / 458 documents.
- Recomputed runtime metrics matched the evaluator exactly, including 529 / 612 / 566 exact entities and F1 0.8981324278.

## Intended Use

Use this model to identify cited news-agency and radio-station source mentions in historical newspaper text. The model is intended for corpus enrichment and assisted curation workflows, not as a general-purpose named-entity recognizer.

The input text should be tokenized with the same annotation-tokenization policy used by the training data. For deployment through the custom pipeline files in this repository, use the model's configured `first_subtoken_viterbi` decoding policy.
