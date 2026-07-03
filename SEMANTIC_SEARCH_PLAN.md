# Semantic Search Sampling Plan

## Purpose

Use Impresso semantic search to broaden the contexts found for a media-source entity without replacing lexical matching or human review. A query such as `Telegraphen-Union` can retrieve semantically related articles, while hierarchical chunk refinement can identify the passage most related to that query.

Semantic similarity is not evidence that an entity is mentioned. Every candidate must still pass the normal matcher/model suggestion and curator review steps.

## Prototype

Run the interactive explorer against the normal API:

```sh
make semantic-search ARGS="--environment normal --language de"
```

For a development API, configure its explicit URL:

```sh
IMPRESSO_DEV_API_URL=https://example.invalid/public-api/v1 \
  make semantic-search ARGS="--environment dev --language de"
```

Alternatively, pass `--api-url` directly. The Impresso client reads a persisted token when available and otherwise prompts for one. Add `--no-persist-token` to avoid storing the entered token.

The prototype workflow is:

1. Enter a semantic query.
2. Embed the query and retrieve the five nearest content items.
3. Select one result or all results.
4. Retrieve the full article text.
5. Split it into overlapping word chunks and embed each chunk.
6. Keep the closest chunk, halve its size, and repeat until the configured minimum or round count is reached.

Useful controls are `--limit`, `--initial-chunk-words`, `--min-chunk-words`, `--rounds`, and `--overlap`.

## Diversity Sampling Design

The production sampler should combine relevance and diversity rather than simply taking the first semantic hits:

1. Retrieve a larger semantic candidate pool, for example 50 to 200 items per query and language.
2. Apply existing eligibility filters: date range, language, available text, issue/date exclusion, sample registry, and document deduplication.
3. Require lexical, contextual-pattern, or current-model evidence for the target entity before creating a review candidate.
4. Represent the relevant article chunk with its embedding.
5. Select the final batch with maximal marginal relevance (MMR): reward similarity to the query while penalizing similarity to already selected samples.
6. Retain the existing language, newspaper, year, and label coverage controls as hard constraints or tie breakers.

A practical MMR score is:

```text
lambda * similarity(query, candidate)
  - (1 - lambda) * max_similarity(candidate, already_selected)
```

Start with `lambda=0.7`: relevance remains dominant, but near-duplicate contexts are disfavored. Compare this with random selection from the same eligible pool.

## Evaluation

For each strategy, record:

- curator acceptance rate;
- unique newspapers, years, and newspaper-date groups;
- duplicate and near-duplicate rate;
- average pairwise embedding similarity within the accepted batch;
- mention-surface and surrounding-context diversity;
- positive yield per API request and per minute of review.

The prototype is successful if it exposes useful passages and different contexts that lexical ranking misses. Production integration is justified only if semantic/MMR sampling improves diversity without materially reducing true-positive yield.

## Risks

- A bare organization name may retrieve topical neighbors that never mention the organization.
- OCR errors can weaken both lexical evidence and embeddings.
- Article-level similarity may be driven by an unrelated section; chunk refinement reduces but does not remove this risk.
- Repeated embedding calls have API and latency costs, so production should cache query and chunk embeddings.
- Semantic retrieval can return text-reuse variants; existing issue and future embedding-near-duplicate checks must remain active.

## Implementation Stages

1. Use the interactive explorer to test representative press-agency and radio-station queries.
2. Save a small comparison set of lexical-only versus semantic candidates and review both blindly.
3. Add cached embeddings and MMR selection to the sampler behind an explicit experimental mode.
4. Add summary fields describing retrieval strategy, semantic score, and diversity penalty.
5. Enable semantic diversification by default only after measured acceptance and diversity results support it.
