# Unify Media-Source Curation Terms And Workflows

## Goal

Simplify the curation workflow so that press agencies, radio stations, and future newspaper mentions use one generic pipeline shape:

```text
sample -> suggest -> review -> split/apply -> preview promotion -> promote
```

The repository should still preserve meaningful entity-family distinctions:

- `pressagency`: labels under `org.ent.pressagency.<canonical_id>`
- `radiostation`: labels under `org.ent.radiostation.<canonical_id>`
- `newspaper`: future labels under the chosen newspaper namespace

The simplification should remove historical command/script duplication where possible. Seed resources should usually remain family-specific because they encode family-specific canonical metadata, aliases, and provenance.

## Recommended Terminology

Use **media-source** for human-facing documentation when clarity matters. It describes the project domain better than the shorter **media**, because the annotations are citations or mentions of sources in historical newspaper text, not generic media content.

Use **media** for short Make targets, file names, and script names where concise command names matter.

Use these names consistently:

| Layer | Preferred term | Examples |
| --- | --- | --- |
| Documentation concept | media-source | "media-source curation", "media-source mention profile" |
| Make target prefix | media | `sample-media-snippets`, `suggest-media-snippet-spans` |
| CLI module prefix | media | `lib.sample_media_snippets`, `lib.score_media_snippets` |
| Family parameter | family | `MEDIA_FAMILY=pressagency`, `--family radiostation` |
| Entity family values | semantic label family | `pressagency`, `radiostation`, `newspaper` |
| Historical compatibility | old command aliases | `sample-newsagency-snippets`, `sample-radio-snippets` |

Also prefer **press agency** over **news agency** in new documentation, help text, and target descriptions. Keep `newsagency` only where it is already part of a compatibility target, old file path, or historical module name during migration.

## Scope

This plan covers dataset curation only:

- snippet sampling from Impresso search
- span suggestion/pre-annotation
- terminal review of sampled or audited candidates
- exporting reviewed snippets into JSONL split rows
- promoting materialized curation output into prerelease/source splits
- curation state and coverage reporting
- docs, Make help, tests, and migration aliases

Out of scope:

- renaming labels such as `org.ent.pressagency.*`
- merging family-specific seed resources
- changing Hugging Face repository names
- changing already published release data
- rewriting historical HIPE import provenance paths unless required by a future cleanup

## Current Problems

The current workbench has one conceptual workflow but several historical names and wrappers:

- press-agency curation is exposed as `newsagency` in Make targets and config variables.
- radio curation has separate `radio` targets and `radiostation` config variables.
- `lib.sample_radiostations` delegates to `lib.sample_newsagencies` instead of a generic sampler.
- `lib.score_radiostation_snippets` reuses pieces from `lib.score_newsagency_snippets`, but both modules keep family-specific logic.
- `lib.review_newsagency_snippets` is already a generic review UI in practice, but its module name and defaults are press-agency-specific.
- `curation_state`, `annotation_stats`, and Make promotion commands hard-code two snippet families.
- future newspaper annotation would add a third copy unless the family concept is made explicit now.

The desired end state is not "one undifferentiated media source type". The desired end state is one generic pipeline parameterized by media-source family.

## Target Workflow

The main generic curation commands should be:

```bash
make annotation-stats
make sample-media-snippets MEDIA_FAMILY=pressagency
make suggest-media-snippet-spans MEDIA_FAMILY=pressagency
make review-media-snippet-spans MEDIA_FAMILY=pressagency REVIEWER="$USER"
make split-media-snippets MEDIA_FAMILY=pressagency
make preview-promote-snippets
make promote-snippets
```

The same shape should work for radio stations:

```bash
make sample-media-snippets MEDIA_FAMILY=radiostation
make suggest-media-snippet-spans MEDIA_FAMILY=radiostation
make review-media-snippet-spans MEDIA_FAMILY=radiostation REVIEWER="$USER"
make split-media-snippets MEDIA_FAMILY=radiostation
make promote-snippets
```

And later for newspapers:

```bash
make sample-media-snippets MEDIA_FAMILY=newspaper
make suggest-media-snippet-spans MEDIA_FAMILY=newspaper
make review-media-snippet-spans MEDIA_FAMILY=newspaper REVIEWER="$USER"
make split-media-snippets MEDIA_FAMILY=newspaper
make promote-snippets
```

Compatibility aliases should remain during the migration:

```bash
make sample-newsagency-snippets      # alias for MEDIA_FAMILY=pressagency
make sample-radio-snippets           # alias for MEDIA_FAMILY=radiostation
make suggest-newsagency-snippet-spans
make suggest-radio-snippet-spans
make review-newsagency-snippet-spans
make review-radio-snippet-spans
make split-newsagency-snippets
make split-radio-snippets
```

These aliases should print the generic replacement in their "Next step" messages once the generic targets are stable.

## Family Configuration Model

Introduce one selected family variable:

```make
MEDIA_FAMILY ?= pressagency
```

Use family-specific variable sets behind it:

```make
PRESSAGENCY_LABEL_METADATA ?= resources/newsagency_seeds.json
RADIOSTATION_LABEL_METADATA ?= resources/radiostation_seeds.json
NEWSPAPER_LABEL_METADATA ?= resources/newspaper_seeds.json

PRESSAGENCY_SNIPPETS ?= data/candidates/pressagency_search_snippets.jsonl
RADIOSTATION_SNIPPETS ?= data/candidates/radiostation_search_snippets.jsonl
NEWSPAPER_SNIPPETS ?= data/candidates/newspaper_search_snippets.jsonl
```

Keep legacy variable aliases while migrating:

```make
NEWSAGENCY_LABEL_METADATA ?= $(PRESSAGENCY_LABEL_METADATA)
NEWSAGENCY_SNIPPETS ?= $(PRESSAGENCY_SNIPPETS)
```

For selected-family targets, derive effective variables using Make conditionals:

```make
MEDIA_LABEL_METADATA = $($(call upper,$(MEDIA_FAMILY))_LABEL_METADATA)
MEDIA_SNIPPETS = $($(call upper,$(MEDIA_FAMILY))_SNIPPETS)
MEDIA_SCORED_SNIPPETS = $($(call upper,$(MEDIA_FAMILY))_SCORED_SNIPPETS)
MEDIA_REVIEWED_SNIPPETS = $($(call upper,$(MEDIA_FAMILY))_REVIEWED_SNIPPETS)
MEDIA_SNIPPET_DECISIONS = $($(call upper,$(MEDIA_FAMILY))_SNIPPET_DECISIONS)
```

Make does not have a simple built-in uppercase function, so implement this either with explicit `ifeq ($(MEDIA_FAMILY),...)` blocks or avoid computed names and pass all selected values through a small Python config resolver. Explicit `ifeq` blocks are more readable and sufficient for three families.

Recommended family values:

| `MEDIA_FAMILY` | Label prefix | Existing seed file | Existing/new path family |
| --- | --- | --- | --- |
| `pressagency` | `org.ent.pressagency.` | `resources/newsagency_seeds.json` | `pressagencies` or transitional `newsagencies` |
| `radiostation` | `org.ent.radiostation.` | `resources/radiostation_seeds.json` | `radiostations` |
| `newspaper` | future newspaper prefix | `resources/newspaper_seeds.json` | `newspapers` |

Prefer new paths under `data/curated/snippets/pressagencies/` for new outputs, but do not move existing curated decisions until there is a deliberate migration step. If preserving existing diffs matters more, keep the old `newsagencies/` directory as the storage location and only change command names first.

## Proposed Script Refactor

### 1. Generic sampler

Create:

```text
lib/sample_media_snippets.py
```

Responsibilities:

- load seed metadata for one `--family`
- derive candidate labels from seed rows
- build alias queries
- call the shared Impresso collection functions currently in `sample_newsagencies.py`
- write selected candidates, sample summary, and registry entries
- support language-aware sampling and `--only-under-target`
- handle rate-limit throttling and graceful Ctrl-C exactly once

Keep thin compatibility wrappers:

```text
lib/sample_newsagencies.py      # wrapper or compatibility module for pressagency
lib/sample_radiostations.py     # wrapper for radiostation
```

Eventually, move shared functions out of `sample_newsagencies.py` into either:

```text
lib/media_sampling.py
```

or keep them in `sample_media_snippets.py` if they are only used there.

### 2. Generic scorer/pre-annotator

Create:

```text
lib/score_media_snippets.py
```

Responsibilities:

- load one or more seed metadata files
- run the configured token-classification model
- add deterministic alias/pattern matches for the selected family
- normalize token/character offsets
- assign curation status (`auto_accepted`, `needs_review`, `removed`, etc.)
- support family-specific boundary normalizers through a small strategy table

Keep thin compatibility wrappers:

```text
lib/score_newsagency_snippets.py
lib/score_radiostation_snippets.py
```

The generic scorer should accept:

```bash
python -m lib.score_media_snippets \
  --family pressagency \
  --input ... \
  --output ... \
  --label-metadata resources/newsagency_seeds.json \
  --aux-label-metadata resources/radiostation_seeds.json \
  --aux-label-metadata resources/newspaper_seeds.json
```

For future newspapers, add a newspaper matcher strategy without adding another top-level scoring module.

### 3. Generic snippet review

Rename implementation intent, not necessarily the file immediately:

```text
lib/review_media_snippets.py
```

Current `lib.review_newsagency_snippets` already behaves generically enough. The migration should:

- move implementation to `review_media_snippets.py`
- leave `review_newsagency_snippets.py` as a wrapper import for compatibility
- make `--family` and `--review-prefix` explicit
- show family-aware label info from the chosen metadata
- support `--review-status needs_review` and `--review-status auto_accepted`

### 4. Generic snippet export/split

`lib/export_snippet_training_data.py` is already largely generic. Keep it, but rename the Make-facing action to `split-media-snippets`.

Small improvements:

- accept `--family` for provenance/source component naming
- canonicalize aliases through a shared label metadata resolver
- always load all configured metadata files for label validation
- preserve current window-repair behavior for human-reviewed spans

### 5. Generic promotion

`lib/promote_snippet_splits.py` is already generic. Keep it as-is except for terminology in docstrings/help if needed.

Promotion should continue to accept repeated `--snippet SPLIT=PATH` arguments. The Make target should assemble all configured family split files.

### 6. Generic state reporting

Update:

```text
lib/curation_state.py
lib/annotation_stats.py
```

The goal is to avoid hard-coded `newsagencies` and `radiostations` argument groups. Use repeatable family specs instead:

```bash
--snippet-family pressagency,candidates=...,summary=...,scored=...,reviewed=...,decisions=...,train=...,validation=...,test=...
--snippet-family radiostation,candidates=...,summary=...,scored=...,reviewed=...,decisions=...,train=...,validation=...,test=...
```

If that is too verbose for Make, use a family config JSON generated from `configs/common.mk` or a small static config file:

```text
configs/media_families.json
```

Do not merge seed resources. The family config should point to them.

## Proposed Make Target Changes

Add generic targets:

```make
sample-media-snippets
sample-freely-media-snippets
suggest-media-snippet-spans
review-media-snippet-spans
review-auto-media-snippet-spans
split-media-snippets
integrate-media-snippets
```

Keep existing aliases:

```make
sample-newsagency-snippets: MEDIA_FAMILY=pressagency
sample-newsagency-snippets: sample-media-snippets

sample-radio-snippets: MEDIA_FAMILY=radiostation
sample-radio-snippets: sample-media-snippets
```

Use the same alias pattern for suggest/review/split.

Update help:

- top-level help should say "media-source curation"
- `help-annotation` should have one "Media-source snippet annotation" section
- add examples with `MEDIA_FAMILY=pressagency` and `MEDIA_FAMILY=radiostation`
- mention that old `newsagency` and `radio` targets remain as aliases during transition

Keep `integrate-snippets` as a convenience target that integrates all configured families. Add `integrate-media-snippets` for one selected family if useful.

## Path Layout Options

### Option A: Rename paths now

New paths:

```text
data/candidates/pressagency_search_snippets.jsonl
data/curated/snippets/pressagencies/
data/candidates/radiostation_search_snippets.jsonl
data/curated/snippets/radiostations/
data/candidates/newspaper_search_snippets.jsonl
data/curated/snippets/newspapers/
```

Pros:

- terminology becomes clean everywhere
- future docs are easier

Cons:

- existing diffs and local curated files move
- aliases need more careful backward-compatible path handling

### Option B: Rename commands first, keep paths initially

Keep:

```text
data/candidates/newsagency_search_snippets.jsonl
data/curated/snippets/newsagencies/
```

but expose them as `MEDIA_FAMILY=pressagency`.

Pros:

- minimal disruption to current prerelease work
- easier to review source-code changes separately from data moves

Cons:

- storage paths remain historically inconsistent for a while

Recommendation: use **Option B first**. Rename paths only after the generic commands and scripts are stable, and do it as a separate data-migration commit.

## Files To Change

### Make/config surface

- `Makefile`
  - add generic media snippet targets
  - keep existing `newsagency` and `radio` aliases
  - simplify `help-annotation`
  - update `.PHONY`
  - make `integrate-snippets` call generic family targets
- `configs/common.mk`
  - add `MEDIA_FAMILY`
  - add selected-family effective variables
  - introduce `PRESSAGENCY_*` variables as preferred names
  - keep `NEWSAGENCY_*` aliases during transition
  - add `NEWSPAPER_*` placeholders without enabling them by default
- `configs/model-v1.0.0.mk`, `configs/model-v2.0.0.mk`
  - only adjust if they override snippet paths or family-specific defaults

### Python modules

- `lib/sample_newsagencies.py`
  - extract shared sampler logic or convert to wrapper
- `lib/sample_radiostations.py`
  - convert to wrapper around generic sampler
- `lib/sample_media_snippets.py`
  - new generic selected-family sampler
- `lib/score_newsagency_snippets.py`
  - extract generic scoring/model helpers or convert to wrapper
- `lib/score_radiostation_snippets.py`
  - convert to wrapper around generic scorer
- `lib/score_media_snippets.py`
  - new generic scorer/pre-annotator
- `lib/review_newsagency_snippets.py`
  - move implementation to generic review module or keep as compatibility wrapper
- `lib/review_media_snippets.py`
  - new generic review module
- `lib/export_snippet_training_data.py`
  - add family-aware provenance/source-component naming if needed
- `lib/curation_state.py`
  - replace hard-coded two-family arguments with configurable families
- `lib/annotation_stats.py`
  - replace `--newsagency-*` and `--radiostation-*` with generic repeatable family inputs
- `lib/validate_dataset_splits.py`
  - keep generic repeated `--snippet` interface; update help text if needed
- `lib/validate_labels.py`
  - optionally accept repeatable `--label-metadata` while preserving old flags

### Tests

- `tests/test_snippet_curation.py`
  - update module imports and add generic-family coverage
- `tests/test_curation_state.py`
  - add three-family state fixture or generic family parsing test
- `tests/test_label_metadata.py`
  - assert family metadata remains separate but conforms to shared schema
- `tests/test_validate_dataset_splits.py`
  - no major changes expected
- Add `tests/test_media_family_config.py`
  - verify family selection resolves the expected paths/metadata
- Add `tests/test_media_sampler.py`
  - verify pressagency and radiostation use the same sampler code path
- Add `tests/test_media_scorer.py`
  - verify family-specific alias matching can be plugged into the generic scorer

### Documentation

- `README.md`
  - change "news agencies and radio stations" to "media-source mentions, currently press agencies and radio stations"
  - prefer "press agency" in new text
  - add generic Make command examples
- `docs/curation.md`
  - replace separate news-agency/radio recipe sections with one generic media-source snippet recipe and family-specific examples
- `docs/workflows.md`
  - update diagrams to show media-source family parameter
- `docs/annotation_guidelines.md`
  - keep family-specific annotation guidelines, but update umbrella terminology
- `docs/data_lifecycle.md`
  - mention generic family-based curation artifacts
- `docs/jsonl_schema.md`
  - make sure `entity_family` values are documented as `pressagency`, `radiostation`, and future `newspaper`
- `AGENTS.md`
  - update repository purpose and curation terminology after implementation

Do not rename `resources/newsagency_seeds.json` immediately unless there is a separate controlled migration. It is a seed-resource filename and can remain historical without blocking generic curation.

## Migration Phases

### Phase 1: Add generic commands without removing old ones

Implement generic `sample-media-*`, `suggest-media-*`, `review-media-*`, and `split-media-*` targets. They should call either new generic scripts or existing scripts via family-specific conditionals.

Acceptance criteria:

- `make sample-media-snippets MEDIA_FAMILY=pressagency ARGS="--dry-run"` works.
- `make sample-media-snippets MEDIA_FAMILY=radiostation ARGS="--dry-run"` works.
- old `sample-newsagency-snippets` and `sample-radio-snippets` still work.
- help text points curators to the generic commands.

### Phase 2: Move implementation behind generic Python modules

Introduce `sample_media_snippets.py`, `score_media_snippets.py`, and `review_media_snippets.py`. Convert old modules to compatibility wrappers.

Acceptance criteria:

- test coverage proves both pressagency and radiostation use the generic code path.
- existing user commands still produce byte-compatible or semantically equivalent outputs.
- review decisions remain append-only and readable by the export step.

### Phase 3: Generalize state and stats

Update `curation_state.py` and `annotation_stats.py` to consume a list of snippet families rather than fixed newsagency/radiostation flags.

Acceptance criteria:

- `make curation-state` output still shows pressagency and radiostation sections.
- adding a newspaper family in config does not require adding another hard-coded argument group.
- JSON output is family-keyed and stable for downstream inspection.

### Phase 4: Documentation cleanup

Update docs to use:

- "media-source" for the umbrella concept
- "press agency" for `org.ent.pressagency.*`
- "radio station" for `org.ent.radiostation.*`
- "newspaper" for future newspaper-source mentions

Acceptance criteria:

- `README.md` top section explains the unified workflow.
- `docs/curation.md` has one generic snippet workflow with family-specific examples.
- old `newsagency` target names are documented only as compatibility aliases.

### Phase 5: Optional path migration

If desired, migrate `newsagency` paths to `pressagency` paths:

```text
data/candidates/newsagency_search_snippets.jsonl -> data/candidates/pressagency_search_snippets.jsonl
data/curated/snippets/newsagencies/ -> data/curated/snippets/pressagencies/
```

Do this only after command and script names are stable. Keep compatibility variables for one release cycle.

Acceptance criteria:

- no curated decisions are lost
- old paths either still work or fail with a clear migration message
- release notes mention the path migration

## Compatibility Policy

Keep old Make targets for at least one dataset release cycle:

- `newsagency` targets become aliases for `MEDIA_FAMILY=pressagency`
- `radio` targets become aliases for `MEDIA_FAMILY=radiostation`

Old Python modules may remain wrappers indefinitely if external scripts use them.

Do not change the label namespace. `org.ent.pressagency.*` is already the correct semantic namespace.

Do not rewrite historical release data to replace `source_component` values unless the release data is being regenerated for another reason.

## Risks

- Make variable indirection can become unreadable. Prefer explicit `ifeq` family blocks over clever computed variable names.
- Renaming paths while prerelease curation is active can lose or hide pending decisions. Keep path migration separate.
- Generic scoring must still preserve family-specific boundary rules. For example, radio aliases and press-agency dotted acronyms may need different normalizers.
- `media` is concise but ambiguous in prose. Use `media-source` in docs.
- Compatibility wrappers can hide technical debt if not documented. Mark them as compatibility shims in code comments and tests.

## Recommended First Implementation Slice

Start with a low-risk facade:

1. Add `MEDIA_FAMILY` and selected-family variables in `configs/common.mk`.
2. Add generic Make targets that dispatch to the existing family-specific scripts.
3. Make old targets aliases to the generic targets.
4. Update help text and `docs/curation.md` to teach generic commands.
5. Add dry-run tests or Make dry-run checks for `pressagency` and `radiostation`.

Only after that, refactor Python modules into generic implementations. This keeps current v2 prerelease curation usable while reducing the command surface immediately.

