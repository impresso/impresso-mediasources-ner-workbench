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

Source model card for the future Hugging Face model repository `impresso-project/mmbert-impresso-mediasources-ner`.

The published model should include:

- model weights
- tokenizer files
- `config.json`
- `requirements.txt`
- `pipeline.py`
- `decoding.py`
- this model card

The first publication is a standard Transformers `token-classification` model. A custom Impresso JSON pipeline will be added later, after the inference interface has been finalized.

The model `config.json` records `annotation_tokenization`, `label_all_tokens`, `subtoken_labeling`, and `subtoken_decoding`. Inference must apply the declared annotation-token profile and the declared `subtoken_decoding` policy. The default deployment policy is `first_subtoken_viterbi`, a constrained BIO decoder over the model label space. `label_all_tokens` describes training supervision; it does not by itself define inference decoding.

The v0.1 model predicts cited source mentions for news agencies and radio stations. The repository name uses "media sources" because the label space may later grow to cover other cited media-source families, such as newspaper citations.

This model is fine-tuned from `impresso-project/mmbert-multilingual-impresso-continued-mlm`, which continued pretraining from `jhu-clsp/mmBERT-base`. The upstream mmBERT base model is released under the MIT license.

## Evaluation

Validation/dev exact entity metrics:

- Precision: 0.8561
- Recall: 0.9040
- F1: 0.8794
- Correct/gold/predicted entities: 113 / 125 / 132

Test exact entity metrics:

- Precision: 0.9111
- Recall: 0.9213
- F1: 0.9162
- Correct/gold/predicted entities: 164 / 178 / 180

These scores are from the legacy converted French/German HIPE-style evaluation splits. Manual disagreement curation is planned after the first publication.
