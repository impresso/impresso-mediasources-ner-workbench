# Streamlined Sampling Plan

## Implementation Status

Implemented in the first focused-sampling pass:

- Smaller routine defaults for press-agency and radio-station sampling.
- Visible `MEDIA_SAMPLE_POOL_FACTOR`.
- `make plan-media-sampling` as a read-only planner.
- `reports.d/sampling/<family>_plan.json` and `.tsv` outputs.
- `sample-media-snippets` consumes the focused sampling plan by default.
- `MEDIA_SAMPLE_MODE=coverage` keeps the older coverage-only behavior.
- `MEDIA_SAMPLE_LABELS` filters both planner and sampler.
- Pending candidate/scored/reviewed/split snippet work is subtracted from planned gaps.
- Mention-surface profiles are used to prefer underrepresented aliases and deprioritize saturated/generic aliases.

Still future work:

- Persistent query-yield history across review/promote cycles.
- More refined language-specific alias scoring.
- Hard skips for historically poor aliases after enough evidence exists.
- A shared sampler core to reduce duplication between press agencies and radiostations.

## Problem

The current sampler is useful but too broad for routine curation. It expands every under-target label/language bucket, tries several aliases per label, builds oversized temporary pools, and only then balances the final output. This creates many API calls and many candidate rows that curators may never review or promote.

The main symptoms are:

- `annotation-stats` reports label-level gaps, but sampling uses label-language gaps. A label with many total examples can still be sampled heavily if one language is below target.
- `target-per-query-lang=5` with the default pool factor collects up to 20 candidates per label/query/language before final selection.
- `max-queries-per-label=3` means one label can generate many searches across five languages.
- The sampler does not use empirical mention-surface profiles, so it may search aliases and surfaces that are already well represented.
- Existing documentation says the routine per-round cap is small, but `NEWSAGENCY_SAMPLE_MAX_PER_LABEL` currently defaults to `20`.

## Goal

Make sampling a focused queue builder:

1. first decide which label/language/surface gaps are worth sampling,
2. search only those gaps,
3. stop as soon as enough useful review candidates exist,
4. make the sampler explain why it searched or skipped each bucket.

The desired result is fewer API calls, fewer low-value candidate snippets, and a clearer path from sampling to review to promotion.

## Principles

- **Coverage first, but not coverage only.** Language-aware coverage remains the main driver, but surface-form diversity should influence which queries are worth trying.
- **Round size should reflect curator capacity.** Defaults should produce a small reviewable batch, not a large backlog.
- **Prefer underrepresented surfaces.** If a label already has many examples of `Havas`, prioritize `Agence Havas`, `(Havas.)`, or language-specific variants only when they are actually missing.
- **Avoid purely generic searches.** Aliases dominated by terms such as `agence`, `agency`, `Agentur`, `radio`, or `Nachrichtenagentur` should be used only when tied to a distinctive name.
- **Make decisions visible.** The sampler summary should report skipped labels, skipped aliases, query priority, and final selected rows.

## Proposed Workflow

The routine workflow becomes:

```bash
make annotation-stats
make mention-profiles
make plan-media-sampling MEDIA_FAMILY=pressagency
make sample-media-snippets MEDIA_FAMILY=pressagency
make suggest-media-snippet-spans MEDIA_FAMILY=pressagency
make review-media-snippet-spans MEDIA_FAMILY=pressagency REVIEWER="$USER"
make integrate-snippets
```

`plan-media-sampling` is a new read-only planning target. It writes a compact JSON/TSV plan that explains exactly which label/language/query buckets the next sampler run will use.

## Implementation Steps

### 1. Align Defaults With Routine Curation

Change routine sampling defaults to a smaller batch:

```make
NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG ?= 2
NEWSAGENCY_SAMPLE_MAX_PER_LABEL ?= 5
NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL ?= 2
NEWSAGENCY_SAMPLE_POOL_FACTOR ?= 2
```

Do the same for radiostations unless there is a family-specific reason to keep a larger batch.

Keep larger batches possible through explicit overrides:

```bash
make sample-media-snippets MEDIA_FAMILY=pressagency MEDIA_SAMPLE_MAX_PER_LABEL=20
```

### 2. Add Pool Factor To Makefile Config

The Python sampler already accepts `--pool-factor`, but the Make target does not expose it. Add:

```make
NEWSAGENCY_SAMPLE_POOL_FACTOR ?= 2
RADIOSTATION_SAMPLE_POOL_FACTOR ?= 2
MEDIA_SAMPLE_POOL_FACTOR ?= ...
```

and pass:

```make
--pool-factor "$(MEDIA_SAMPLE_POOL_FACTOR)"
```

This turns the current implicit pool target of `5 * 4 = 20` into a visible, configurable setting.

### 3. Add A Sampling Planner

Create `lib.plan_media_sampling` with inputs:

- `data/curated/annotation_coverage.json`
- `reports.d/entity-mention-profiles/profiles.json`
- family seed metadata, for example `resources/newsagency_seeds.json`
- existing sample registry
- current candidate/reviewed snippet files

Outputs:

- `reports.d/sampling/pressagency_plan.json`
- `reports.d/sampling/pressagency_plan.tsv`
- terminal summary

The plan should rank candidate searches by:

- missing count for the label/language bucket,
- whether the surface or alias is underrepresented for that label,
- whether the alias is language-appropriate,
- whether previous searches for this label/language/query produced useful accepted rows,
- whether the query is distinctive enough to avoid noisy generic hits.

### 4. Use Surface Profiles To Prioritize Queries

Extend mention profiles or add a small helper that provides per label/language:

- accepted surface counts,
- normalized surface counts,
- top surfaces,
- singleton surfaces,
- generic-term inclusion rate,
- surface-language distribution.

Then classify seed aliases into:

- **underrepresented**: alias/surface has few or no accepted examples in that language,
- **represented**: already enough examples for this surface/language,
- **generic-risk**: likely too broad without a distinctive token,
- **unknown**: no evidence yet.

The sampler should prefer `underrepresented` and `unknown`, deprioritize `represented`, and skip `generic-risk` unless explicitly requested.

### 5. Make Query Selection Gap-Aware

Currently `max-queries-per-label` is applied before knowing which aliases are useful. Replace or augment this with query planning:

- For each label/language bucket, compute missing count.
- Choose at most `N` query strings for that label/language.
- Prefer aliases matching the target language.
- Prefer aliases not already dominant in accepted data.
- Avoid aliases with historical poor yield.

For example, if `Reuters` is already well represented but `Reutermeldung` is not, use `Reutermeldung` for German only. If `Havas` is saturated but `Agence Havas` is underrepresented in French, search `Agence Havas` only for French.

### 6. Stop Earlier During Collection

For each label/language bucket:

- stop once the planned target has enough candidates,
- stop if the bucket already has enough pending sampled or reviewed rows,
- stop after repeated pages with no new eligible issue/entity pair,
- skip full-content fetches until after a search hit passes cheap filters.

This keeps expensive content fetches for candidates that are likely to survive deduplication.

### 7. Count Pending Work Against Sampling Need

Before sampling more, subtract existing work from the missing count:

- candidates in `data/candidates/*_search_snippets.jsonl`,
- scored rows needing review,
- reviewed accepted rows not yet split/promoted,
- split snippet rows not yet promoted.

The planner should report:

```text
missing_gold=8 pending_sampled=3 pending_review=2 planned_new=3
```

This avoids creating more snippets when the backlog already fills the gap.

### 8. Track Search Yield

Extend the sample summary and registry with query-level outcomes:

- searched pages,
- raw hits,
- candidates after dedupe,
- selected candidates,
- reviewed accepted/rejected when available,
- promoted rows when available.

Use this to avoid repeatedly searching aliases that historically produce zero usable rows.

### 9. Add Explicit Sampling Modes

Keep one routine target and add mode controls:

- `MEDIA_SAMPLE_MODE=focused`: default; uses coverage, pending work, surface profiles, and yield history.
- `MEDIA_SAMPLE_MODE=coverage`: current label/language coverage behavior, but with smaller defaults.
- `MEDIA_SAMPLE_MODE=surface`: prioritize underrepresented surface forms for one or more labels.
- `MEDIA_SAMPLE_MODE=free`: explicit broad exploration.

This avoids overloading one target with hidden behavior.

### 10. Improve Terminal Output

Replace noisy pool logs with planning-oriented output:

```text
Sampling plan: pressagency
label                         lang  missing  pending  planned  query
org.ent.pressagency.stefani   fr    4        1        2        Agence Stefani
org.ent.pressagency.ata       de    1        0        1        Albanische Nachrichtenagentur

Skipped:
org.ent.pressagency.reuters   de    enough surface coverage for Reuters
org.ent.pressagency.havas     fr    pending review already fills gap
```

Keep verbose API logs available with `MEDIA_SAMPLE_VERBOSE=true`.

## Files To Change

- `configs/common.mk`
  - reduce routine sampling defaults,
  - expose `*_SAMPLE_POOL_FACTOR`,
  - add plan output paths and sampling mode variables.

- `Makefile`
  - pass `--pool-factor`,
  - add `plan-media-sampling`,
  - make `sample-media-snippets` optionally depend on or consume the plan,
  - update help text.

- `lib/sample_newsagencies.py`
  - consume planned query buckets,
  - account for pending work,
  - reduce noisy logging unless verbose mode is enabled,
  - record query-yield statistics.

- `lib/sample_radiostations.py`
  - apply the same logic or refactor shared code first.

- `lib/sample_media_snippets.py`
  - keep family dispatch, but allow common planner arguments.

- `lib/entity_mention_profiles.py`
  - ensure profile JSON exposes enough per-label/per-language surface counts for planning.

- New `lib/plan_media_sampling.py`
  - read coverage, mention profiles, seed metadata, pending snippets, and registry,
  - write sampling plan JSON/TSV.

- `docs/curation.md`
  - document focused sampling,
  - explain the difference between coverage gaps, surface gaps, and free sampling.

- Tests
  - planner ranking tests,
  - pending-work subtraction tests,
  - generic alias skip tests,
  - Make dry-run or CLI argument tests for pool factor and modes.

## Suggested Rollout

1. **Small config cleanup first.**
   - Expose `MEDIA_SAMPLE_POOL_FACTOR`.
   - Lower default routine caps.
   - Update docs so defaults match reality.

2. **Add planner as read-only diagnostic.**
   - Do not change sampling behavior yet.
   - Compare plan output with curator expectations.

3. **Make sampler consume explicit plan files.**
   - Keep current behavior available with `MEDIA_SAMPLE_MODE=coverage`.

4. **Add surface-aware query pruning.**
   - Start with conservative prioritization, not hard skipping.
   - Add hard skips only for clearly generic/no-yield aliases.

5. **Use yield history and pending backlog.**
   - Prevent repeated low-value searches.
   - Keep the review queue small and actionable.

## Open Questions

- What is the preferred routine review batch size per curator session: 20 rows total, 50 rows total, or 5 rows per label?
- Should side languages (`lb`, `it`) be sampled only on explicit request once the main languages are healthy?
- Should surface-form targets be hard numeric targets or soft diversity priorities?
- Should the sampler avoid labels above the global target unless the user explicitly enables language balancing?
- Should query-yield history live in `reports.d/`, `audit.d/`, or the existing sample registry?
