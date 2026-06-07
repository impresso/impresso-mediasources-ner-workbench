# AGENTS.md

## Repository Purpose

This repository is the workbench for a joint Impresso media-source mention NER project covering:

- news agencies, labelled as `org.ent.pressagency.<canonical_id>`
- radio stations, labelled as `org.ent.radiostation.<canonical_id>`

The workbench is the control plane. It owns sampling, curation, dataset export, release configs, tests, and source copies of Hugging Face cards and pipeline code. Published datasets, frozen test sets, and model payloads belong on Hugging Face.

## Command Policy

When running local project commands yourself, use `remake` instead of `make`.

Examples:

- Use `remake test`
- Use `remake smoke`
- Use `remake publish-dataset ARGS="--dry-run"`

When editing files intended for users, documentation, release notes, README examples, Makefile help text, or shell snippets, write commands as `make`, not `remake`.

Do not mention `remake` in public-facing documentation unless explicitly asked.

## Current Shape

The current repo is scaffolded. Implementation should follow `WORKBENCH_PLAN.md`.

Important paths:

```text
lib/                 # workbench commands and shared helpers
resources/           # canonical labels, seeds, and curation policy
data/                # local candidate, curated, and held-out data
hf_dataset/          # source training dataset card
hf_testset/          # source testset card
hf_model/            # source model card and HF pipeline
configs/             # release configs
training/            # future training-code submodule
pipeline/            # future impresso-pipelines reference submodule/symlink
hub/                 # future HF repo submodules
tests/               # smoke and contract tests
```

## Data Policy

- Training and inference artifacts are JSONL.
- `unk`, unresolved bare `ag`, and `pers.ind.articleauthor` are not trainable output labels.
- News-agency metadata starts from `resources/newsagency_seeds.json`.
- Radio-station metadata starts from `resources/radiostation_seeds.json`.
- Wikipedia/Wikidata links are metadata requirements for concrete news-agency labels.
- Curation must preserve original candidate rows and append decisions instead of destructively rewriting evidence.

## Curation Terminology

Use these terms consistently in code, comments, and documentation:

- **export**: convert reviewed snippet decisions into standalone JSONL rows (`export-newsagency-snippets`, `export-radiostation-snippets`).
- **apply**: convert reviewed span-patch or existing-span decisions into a patched JSONL split (`apply-span-patches`, `apply-existing-spans`).
- **promote**: integrate the materialized result (exported rows or patched split) into the configured prerelease/source split that training, export, and publishing will use (`promote-snippets`, `promote-span-patches`, `promote-existing-spans`).
- **refresh-\***: convenience shortcut that materializes reviewed decisions and then promotes them in one step.

Promotion is the single integration point. Nothing enters the dataset split until a `promote-*` or `refresh-*` target runs.

See [docs/curation.md](docs/curation.md) for the full workflow, path selection table, and quick recipes.

## Command Defaults

Command examples in this repo omit `PYTHON=.venv/bin/python` and `CFG=configs/model-v2.0.0.mk` because both are the Makefile defaults. Pass them only when you need a non-default interpreter or release config. Review targets require `REVIEWER="$USER"` (or any short identifier) to tag decisions.

## Implementation Notes

- Keep the first implementation ModernBERT token-classification only.
- Do not add TorchServe support unless explicitly requested later.
- Adapt the existing `impresso-pipelines` news-agency pipeline into a self-contained Hugging Face pipeline.
- Keep source copies of HF cards and pipeline code in this workbench; use publish scripts to stage them into HF repos.
- Add tests before changing token/span alignment, offset handling, or label-map generation.
