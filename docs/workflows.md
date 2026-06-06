# Workbench Workflows

This document gives a compact view of the main workbench activities. The workbench is the control plane: it creates and curates local JSONL artifacts, trains/evaluates models, and stages published Hugging Face dataset and model repositories.

In diagrams and prose, **HIPE-derived data** means the converted French/German news-agency annotations imported from the earlier HIPE/CoNLL-style source files. This data is still an active baseline training and evaluation source. Some local paths and commands keep the historical `legacy-*` name for compatibility.

## Overall Activities

```mermaid
flowchart TD
  A[Canonical metadata and policy] --> B[Candidate sampling]
  A --> C[HIPE source import]
  B --> D[Pre-annotate sampled candidates]
  C --> E[HIPE-derived JSONL folds]
  D --> F[Span review]
  E --> G[HIPE dev/test correction]
  F --> H[Snippet-derived JSONL rows]
  G --> I[Curated HIPE-derived JSONL rows]
  H --> J[Training dataset staging]
  I --> J
  J --> K[Publish training dataset]
  J --> L[Train token-classification model]
  M[Impresso MLM source text] --> N[Continued MLM data]
  N --> O[Domain-adapted base model]
  O --> L
  L --> P[Evaluate model]
  P --> Q[Publish model and HF pipeline]
  Q --> D
```

## Create Or Update Datasets

```mermaid
flowchart TD
  A[HIPE TSV or curated HIPE-derived JSONL] --> B[Import or apply corrections]
  B --> C[Curated HIPE-derived JSONL]
  D[Reviewed sampled spans] --> E[Snippet-derived train/test JSONL]
  C --> F[Dataset export]
  E --> F
  F --> G[Staged HF dataset directory]
  G --> H[Dry-run validation]
  H --> I[Publish dataset or open PR]
```

Primary commands:

```bash
make import-legacy-hipe ARGS="..."
make apply-curation CFG=configs/model-v0.1.0.mk
make export-newsagency-snippets CFG=configs/model-v0.1.0.mk
make export-radiostation-snippets CFG=configs/model-v0.1.0.mk
make publish-dataset CFG=configs/model-v0.1.0.mk ARGS="--dry-run"
```

## Create, Pre-Annotate, And Review Sampled Data

```mermaid
flowchart TD
  A[Label metadata and aliases] --> B[Sample Impresso candidates]
  B --> C[Normalize text window]
  C --> D{Entity family}
  D -->|News agency| E[ModernBERT span proposals]
  D -->|Radio station| F[Alias spans plus optional ModernBERT spans]
  E --> G[Scored candidate JSONL]
  F --> G
  G --> H{Curation status}
  H -->|auto_accepted| I[Accepted spans]
  H -->|needs_review| J[Terminal span review]
  J --> I
  J --> K[Rejected, skipped, or removed audit rows]
  I --> L[Export train/test JSONL]
```

Primary commands:

```bash
make sample-newsagencies CFG=configs/model-v0.1.0.mk
make score-newsagency-snippets CFG=configs/model-v0.1.0.mk
make review-newsagency-snippets CFG=configs/model-v0.1.0.mk REVIEWER="$USER"
make export-newsagency-snippets CFG=configs/model-v0.1.0.mk

make sample-radiostations CFG=configs/model-v0.1.0.mk
make score-radiostation-snippets CFG=configs/model-v0.1.0.mk
make review-radiostation-spans CFG=configs/model-v0.1.0.mk REVIEWER="$USER"
make export-radiostation-snippets CFG=configs/model-v0.1.0.mk
```

## Correct HIPE-Derived Dev/Test Data

```mermaid
flowchart TD
  A[HIPE-derived validation/test JSONL] --> B[Run selected model]
  B --> C[Prediction JSONL]
  A --> D[Gold spans]
  C --> E[Gold-vs-prediction disagreements]
  D --> E
  E --> F[Terminal review]
  F --> G[Append-only decisions]
  G --> H[Validate decisions]
  H --> I[Apply decisions non-destructively]
  I --> J[Curated HIPE-derived validation/test JSONL]
  I --> K[Audit files]
```

Primary commands:

```bash
make curate-legacy-eval CFG=configs/model-v0.1.0.mk CURATION_MODEL=models/newsagency_radiostation_modernbert_v0.1.0_continue1/best
make review-curation CFG=configs/model-v0.1.0.mk REVIEWER="$USER"
make validate-curation CFG=configs/model-v0.1.0.mk
make apply-curation CFG=configs/model-v0.1.0.mk
```

## Create Or Update Models

```mermaid
flowchart TD
  A[Compiled Impresso MLM source text] --> B[Build MLM data]
  B --> C[Continue MLM pretraining]
  C --> D[Domain-adapted base model]
  E[Curated training JSONL] --> F[Supervised token-classification training]
  D --> F
  F --> G[Validation and early stopping]
  G --> H[Best local checkpoint]
  H --> I[Official test evaluation]
  I --> J[Metrics and predictions]
  H --> K[Stage HF model payload]
  J --> K
  L[HF pipeline source] --> K
  K --> M[Push model to Hugging Face]
```

Primary commands:

```bash
make download-mlm-sources CFG=configs/model-v0.1.0.mk
make build-mlm-data CFG=configs/model-v0.1.0.mk
make pretrain-mlm CFG=configs/model-v0.1.0.mk
make push-mlm-model CFG=configs/model-v0.1.0.mk
make train CFG=configs/model-v0.1.0.mk
make test CFG=configs/model-v0.1.0.mk
make test-official CFG=configs/model-v0.1.0.mk
make push-model CFG=configs/model-v0.1.0.mk
```

## Publish Artifacts

```mermaid
flowchart TD
  A[Curated dataset source] --> B[Dataset staging preflight]
  B --> C[HF training dataset repo]
  D[Held-out testset source] --> E[Testset staging preflight]
  E --> F[HF testset repo]
  G[Model checkpoint, metrics, card, pipeline] --> H[Model preflight]
  H --> I[HF model repo]
  C --> J[Recorded dataset revision]
  F --> K[Recorded testset revision]
  I --> L[Recorded model revision]
```

Primary commands:

```bash
make publish-dataset CFG=configs/model-v0.1.0.mk ARGS="--dry-run"
make publish-testset CFG=configs/model-v0.1.0.mk ARGS="--dry-run"
make push-model CFG=configs/model-v0.1.0.mk
```
