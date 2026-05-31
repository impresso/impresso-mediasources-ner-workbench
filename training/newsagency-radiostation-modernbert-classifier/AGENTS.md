# AGENTS.md

## Scope

This training package owns ModernBERT-only token classification for Impresso news-agency and radio-station source mentions.

## Command Policy

When running local project commands yourself from this repository, use `remake` instead of `make` if a Makefile is present.

When editing user-facing documentation or shell snippets, write commands as `make`, not `remake`.

## Training Data

The primary input is the workbench JSONL format documented at:

```text
../../docs/jsonl_schema.md
```

Do not train labels for:

- `*.unk`
- unresolved bare `ag`
- `pers.ind.articleauthor`
- generic organization labels

The training code must load labels from `label_map.json` and must not hard-code label IDs.
