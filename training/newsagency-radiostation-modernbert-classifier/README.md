# Newsagency Radiostation ModernBERT Classifier

Multilingual ModernBERT-family token-classification training package for the Impresso media sources NER workbench. The default base model is `jhu-clsp/mmBERT-base`.

## Install

From the workbench root:

```bash
python -m pip install -e ".[hf]"
python -m pip install -e training/newsagency-radiostation-modernbert-classifier
```

## Train

```bash
make train CFG=configs/model-v0.1.0.mk
```

The workbench target uses `data/curated/legacy-import/{train,validation,test}.jsonl` and writes a model under `models/`.

## Evaluate

```bash
make test CFG=configs/model-v0.1.0.mk
```

Evaluation writes metrics and prediction JSONL files under the model directory.
