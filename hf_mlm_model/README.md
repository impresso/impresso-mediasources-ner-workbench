---
language:
- fr
- de
- en
- lb
base_model: jhu-clsp/mmBERT-base
library_name: transformers
license: mit
tags:
- modernbert
- mmbert
- masked-language-modeling
- impresso
---

# multilingualmodernimpressoBERT

Source card for the future Hugging Face model repository:

```text
impresso-project/mmbert-multilingual-impresso-continued-mlm
```

This model is a continued-MLM adaptation of `jhu-clsp/mmBERT-base` on multilingual Impresso newspaper text.

The checkpoint is intended as a domain-adapted base model for downstream media-agency token classification.

## License

This continued-pretraining checkpoint is released under the MIT license, matching the license of the base model `jhu-clsp/mmBERT-base`.

The model is derived from `jhu-clsp/mmBERT-base`; users should cite and comply with the base model terms. The continued-MLM training corpus consists of Impresso newspaper text samples used for domain adaptation. The model weights are published separately from the source text; users remain responsible for checking whether their downstream use of Impresso-derived models and outputs is compatible with their institutional, corpus, and application-specific requirements.

## Continued MLM Run

The first completed workbench run used:

- source compiled Impresso files: `fr`, `de`, `en`, `lb`
- source filtering: OCR quality at least `0.90`, minimum text length `200` characters
- source sampling policy: up to 300,000 texts per language, with smaller languages exhausted
- sampled corpus: 872,889 train rows and 8,818 validation rows after split
- training subset: 100,000 train rows
- validation subset: 2,000 validation rows
- base model: `jhu-clsp/mmBERT-base`
- objective: masked language modeling
- MLM probability: `0.15`
- max sequence length: `256`
- padding: fixed max-length padding
- epochs: `1`
- per-device train batch size: `1`
- gradient accumulation steps: `8`
- effective train batch size per device: `8`
- gradient checkpointing: enabled
- learning rate: `2e-5`
- weight decay: `0.01`
- warmup: 750 steps, computed as 6 percent of the capped optimizer steps
- intermediate checkpoint saving: disabled; final model only
- random seed: `42`

Training was run locally on Apple Silicon using the PyTorch MPS backend. The completed run took about 8 hours and 6 minutes. Observed memory use stayed below roughly 30 GB.

## Metrics

Final run metrics:

| metric | value |
| --- | ---: |
| train loss | 1.7775 |
| eval loss | 1.7172 |
| train runtime | 29,134 seconds |
| train samples / second | 3.432 |
| train steps / second | 0.429 |
| eval samples / second | 14.885 |

The validation loss stayed close to the train loss and the run completed without divergence, so this checkpoint is suitable for downstream comparison against the original `jhu-clsp/mmBERT-base`.
