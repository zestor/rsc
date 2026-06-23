# People research

End-to-end recipe for finding people meeting a set of criteria — hiring sourcing, alumni discovery, expert finding, investor / partner mapping, named-person verification. Composes `pplx_sdk.search.people` with the auxiliary content methods to get from a broad query to a precise, enriched list.

## Tool selection

The People index (`pplx_sdk.search.people`, see `reference/search.md`) is strongest on intersection-style queries (`company × role`, `role × company × location`). Supplement with `pplx_sdk.search.web` when:

- The query targets a specific organization's team / about / partners page (VC partner lists, lab group pages, C-suite rosters).
- Criteria need temporal awareness ("currently at X", "left Y in 2024").
- The domain is niche academic (specific lab, conference community, thesis topic).
- `search.people` returns many results but few true matches after filtering.

For comprehensive searches, run both in parallel and merge.

## Variation axes

A single `search.people` query misses some relevant people; run 3+ parallel variants across these axes (fan out via `patterns/fanout.md`):

- **Role titles + acronyms** — `PM` / `product manager` / `product lead`.
- **Company name forms** — acronym / full name / common abbreviations.
- **Industry terms** — acronym / expansion.
- **Scope slicing** — team, geography, seniority.

Skip the acronym/expansion pairing only when the company is best known by its acronym.

## Field filters: supplement, not replacement

`search.people` accepts auxiliary filter kwargs (`name`, `company`, `skills`, `location`, `education`) that scope results to people whose profile fields match all of the provided tokens. Each filter is whitespace-tokenized and ANDed as `contains` clauses against the target field(s).

**Filters scope, the ranker handles fuzzy match.** Use filters *as additional fan-out variants alongside* plain-text queries, not instead of them — filters hit a narrower index slice and miss profiles the plain-text search would find.

- **Add a filter** when the criterion is structural (company affiliation, location, alumni status) AND the plain-text query alone returns too much noise. Filters scope crisply and don't compete with the ranker.
- **Keep it in the query** when the criterion is semantic ("senior", "fintech", "AI safety"). The ranker handles fuzzy matches the filter index can't.

Pattern: fan filtered variants alongside the plain-text query, deduped by URL after merge.

## Pipeline

Four steps. Write each as a script under `$RD/scripts/` (see `patterns/multi-step.md` → Script Discipline).

1. **Search + dedup** (`01_search.py`) — call `search.people_many` with 3+ query variants across the axes above (scale to breadth: 3–5 for moderate searches, up to 10 for broad sweeps). Dedup the merged hits by URL keeping the longest summary (see `patterns/multi-step.md` → Dedup). Output: `$RD/deduped.jsonl`.

2. **Enrich with fetch_people** (`02_enrich.py`) — load `$RD/deduped.jsonl`, call `pplx_sdk.content.fetch_people` in chunks of 50 over all deduped URLs. Each row keeps its original search fields **plus** `full_name`, `current_companies`, `previous_companies`, `education_ongoing`, `education_finished`, `skills` (when the fetch succeeded). Rows where fetch returned `error: "not found"` keep just the search fields. No LLM cost. Output: `$RD/enriched.jsonl`.

   This step is what lets the filter phrase exclusions against fielded data (company history, education) instead of the free-text summary alone.

3. **Filter** (`03_filter.py`) — load `$RD/enriched.jsonl`, run the resumable filter pattern from `patterns/checkpoint.md`. Anchor the instruction on `summary` **and** the enrichment fields where they sharpen the call (`current_companies`, `education_finished`, etc.). Phrase exclusions ("drop if not X"). After the resumable run, flatten `Checkpoint.read_all()` into `$RD/matches.jsonl` (matching rows with the original enriched fields plus classifier output) and `$RD/errors.jsonl` so step 4 has stable input. Re-running this script after a `bash()` timeout is safe — `Checkpoint` skips already-done batches.

   **The filter step is not optional.** `search.people` returns many loosely-matching profiles; without filtering, expect significant noise.

4. **Dossier enrichment** (`04_dossier.py`, conditional) — required when the deliverable needs **publications, bio, exact tenure dates**, or any field outside `fetch_people`'s fixed set. Load `$RD/matches.jsonl`, call `pplx_sdk.content.fetch_many` on the URLs, then `pplx_sdk.llm.extract_many` against a richer schema (use `patterns/checkpoint.md` framing whenever the pool is large enough to risk a `bash()` timeout — see `reference/llm.md` → Larger Pools). Write the flattened result to `$RD/dossiers.jsonl`.

   If a fetch returns a login wall or empty content, fall back to `pplx_sdk.search.people("<name> <company> <field>")` or `browser_task` if available. **Do not fill dossier fields from the search summary** — the model will emit `"unknown"` and it will ship.

Build the final deliverable from `dossiers.jsonl` when step 4 ran, otherwise from `matches.jsonl`.

## Named person lookup (no pipeline)

When the task names a specific person, start with a single `search.people` call:

```python
hits = pplx_sdk.search.people("Jane Doe Acme Corp", limit=10)
```

If multiple plausible profiles come back (common name, ambiguous identity), disambiguate by adding company, location, education, or `skills` filters, or run a web search for a canonical profile URL before continuing. No dedup, no filter pipeline, no enrichment unless the deliverable needs more than the summary — in which case skip straight to dossier.

## Combined search (web → fetch → people)

When the target organization has a public team / about / partners page that lists names directly:

1. `pplx_sdk.search.web("{company} {role} team", domains=["{company-domain}"])` — find team pages, directories, press releases.
2. `pplx_sdk.content.fetch_many(urls)` — read pages; extract names from `content` (often with `pplx_sdk.llm.extract` and a `{names: [...]}` schema).
3. `pplx_sdk.search.people("{name} {company}", limit=10)` — enrich each named candidate.

This is also useful when `search.people` alone has poor recall for the target (very senior executives, public figures, niche academic).

## Gotchas

- **Never fabricate email addresses from patterns.** `firstname.lastname@company.com` guesses are unverified and have reached deliverables in past audits. Either resolve via `pplx_sdk.content.snippets` on the profile URL, or deliver the profile URL only and label every row `email_verified: false`.
- **Names are often truncated** ("First L" instead of full name). Resolve via `pplx_sdk.content.snippets` on the profile URL — `snippets` returns focused extracts that often include the full name even when the search summary doesn't.
- **High noise at `limit=100`.** Requesting 100 results returns 100 keyword-matched profiles, not 100 relevant ones. The filter step handles precision — don't tighten the search query to compensate.
