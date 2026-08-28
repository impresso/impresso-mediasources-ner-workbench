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

The v2.0.1 model predicts cited source mentions for:

- news agencies, labelled as `org.ent.pressagency.<canonical_id>`
- radio stations, labelled as `org.ent.radiostation.<canonical_id>`

The repository name uses "media sources" because the label space may later grow to cover other cited media-source families.

## Provenance

- Dataset: `impresso-project/impresso-mediaagencies-ner-dataset`
- Dataset revision: `v2.0.0`
- Dataset commit: `a7ac5dc1ec0dd92ae848dbccd258aa0361830da3`
- Training code commit: not recorded by this completed run
- Publication/workbench commit: `429a3767288abd16a43b2f7996453f73df350c7c`
- Model revision: `v2.0.1`
- Model commit: `5f600305a86b90d5467c5d71b827e0f33872776c`
- Previous model commit: `9899ad960b9bc310ee51cd7ee658fd3882b6b140`
- Base model: `impresso-project/mmbert-multilingual-impresso-continued-mlm`
- Upstream base: `jhu-clsp/mmBERT-base`
- License: MIT

The model was trained from the pinned published Hugging Face dataset commit above. The selected checkpoint was chosen on validation performance, not on the held-out test set. The completed training run did not record a Git SHA in `training_start_report.json`; the publication/workbench commit is therefore recorded separately and should not be treated as the exact training-code commit. The v2.0.1 revision updates the Hugging Face custom pipeline runtime for the existing v2.0.0 trained weights; no retraining was performed.

## Training Setup

- Annotation tokenization: `unicode-word-punctuation-v1`
- Subtoken supervision: all subtokens labelled, with B-to-I conversion for continuation subtokens
- Decoder used for evaluation/deployment: `first_subtoken_viterbi`
- Adaptation: top 4 ModernBERT layers unfrozen

The model `config.json` records `annotation_tokenization`, `label_all_tokens`, `subtoken_labeling`, and `subtoken_decoding`. Inference must apply the declared annotation-token profile and the declared `subtoken_decoding` policy. `label_all_tokens` describes training supervision; it does not by itself define inference decoding.

## Model Selection Experiments

The released protocol was chosen through validation-only experiments. The held-out test set was not used for selecting the supervision strategy, decoder, or context-window parameters.

A decoder/supervision experiment compared the released all-subtoken B-to-I training supervision against first-subtoken-only supervision. The released model uses all-subtoken B-to-I supervision, so the most relevant decoder comparison is within that supervision regime.

`first_subtoken` decoders use only the first model subtoken as word-level evidence, while `all_subtoken` decoders aggregate evidence from all model subtokens belonging to an annotation token. The `_viterbi` variants additionally enforce the BIO sequence constraints:

- `first_subtoken`: raw argmax on the first subtoken of each word.
- `first_subtoken_viterbi`: BIO-constrained Viterbi over first-subtoken emissions.
- `all_subtoken`: raw argmax over legal all-subtoken word-expansion emissions.
- `all_subtoken_viterbi`: BIO-constrained Viterbi over all-subtoken word-expansion emissions.

Under all-subtoken B-to-I supervision, the validation means across three seeds were:

- `first_subtoken_viterbi`: entity F1 `0.934203`
- `all_subtoken_viterbi`: entity F1 `0.931488`
- `first_subtoken`: entity F1 `0.909763`
- `all_subtoken`: entity F1 `0.909749`

The strongest validation setting was therefore all-subtoken B-to-I supervision with `first_subtoken_viterbi` decoding. Replacing `first_subtoken_viterbi` with raw first-subtoken argmax reduced validation entity F1 by about 2.4 points on average. The unconstrained `all_subtoken` argmax decoder performed similarly to first-subtoken argmax, while `all_subtoken_viterbi` was close but did not improve over `first_subtoken_viterbi`.

The broader experiment also showed that all-subtoken inference decoders are not compatible with first-subtoken-only training supervision. With first-subtoken-only supervision, continuation subtokens are not trained as word-level label evidence, and consuming those positions during all-subtoken decoding substantially degrades performance. Runtime decoding should therefore follow the model-configured `subtoken_decoding` policy rather than treating decoder choice as interchangeable post-processing.

A context-window experiment then compared 512, 1024, and 2048 token window configurations under the selected supervision and decoder. Maximum sequence length, words per window, and stride scale together in these settings. The 512-token setting remained best on validation:

- `512/256/32`: mean entity F1 `0.934203`
- `1024/512/64`: mean entity F1 `0.932313`
- `2048/1024/128`: mean entity F1 `0.926514`

A separate inference-context matrix evaluated already trained 512-, 1024-, and 2048-context models with 512, 1024, and 2048 inference windows. Longer inference windows did not improve performance, including for the 512-trained model, but results were stable across reasonable window settings: mean entity F1 ranged from `0.924440` to `0.934203`. The selected default `512/256/32` is therefore both the best validation setting and a conservative efficient choice.

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

- Release-artifact inference was verified on the complete v2.0.0 held-out test set for the published v2.0.1 runtime artifact.
- The Hugging Face runtime pipeline matched the evaluator's decoded BIO sequence for 458 / 458 documents.
- Recomputed runtime metrics matched the evaluator exactly, including 529 / 612 / 566 exact entities and F1 0.8981324278.

## Intended Use

Use this model to identify cited news-agency and radio-station source mentions in historical newspaper text. The model is intended for corpus enrichment and assisted curation workflows, not as a general-purpose named-entity recognizer.

The input text should be tokenized with the same annotation-tokenization policy used by the training data. For deployment through the custom pipeline files in this repository, use the model's configured `first_subtoken_viterbi` decoding policy.
