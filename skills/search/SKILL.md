# Overview

Use this skill to search Perplexity indexes, fetch full page content or query-dependent page excerpts from URLs, use LLM to postprocess search results and content, and orchestrate multi-step research workflows.

Access search capabilities via the pre-installed `pplx_sdk` Python library.

## How To Use

Example of simple web-search call:

```bash
python -m pplx_sdk.exec << 'PY'
save_and_print(pplx_sdk.search.web("python release notes", limit=3))
PY
```

`pplx_sdk.exec` is a lightweight helper for small snippets; it pre-imports `pplx_sdk` and `save_and_print`.

Always include `api_credentials=["pplx-sdk"]` in your `bash()` call to access the SDK, otherwise any attempt to use `pplx_sdk` will fail with an authentication error:

```python
bash(
    command=(...),
    api_credentials=["pplx-sdk"],
    ...
)
```

## One-Off SDK Calls

Use `pplx_sdk.exec` for small search/fetch snippets that fit in one `bash()` call:

- **Web search** - `save_and_print(pplx_sdk.search.web("query", limit=10))`
- **Domain filter** - `save_and_print(pplx_sdk.search.web("query", domains=["github.com", "stackoverflow.com"]))`
- **Exclude domains** - `save_and_print(pplx_sdk.search.web("query", excluded_domains=["pinterest.com", "quora.com"]))`
- **Academic / images / videos / shopping** - same shape as `save_and_print(pplx_sdk.search.academic("query", limit=10))`; replace `academic` with the needed index.
- **People search** - `save_and_print(pplx_sdk.search.people("product manager fintech London", limit=10))`
- **Fetch URL content** - `save_and_print(pplx_sdk.content.fetch(["https://example.com"], cache_enabled=False))`
- **Snippets from URL** - `save_and_print(pplx_sdk.content.snippets(query="query", urls=["https://example.com"]))`

Use short keyword queries, usually 2-5 meaningful words. Do not use quote marks, exact-phrase syntax, `site:`, or boolean `OR` / `AND`; use SDK args such as `domains` and `excluded_domains` instead. Fetch results carry page body in `content`; snippets carry focused excerpts in `text`.

Keep one-off snippets to a single SDK expression wrapped in `save_and_print(...)`. Do not add imports, loops, manual JSON printing, or post-processing logic. If you need intermediate variables, joins, filtering, retries, or multiple SDK calls, write a saved Python script and use `patterns/multi-step.md`.

`save_and_print(...)` saves the full JSON response to an auto-generated file path and prints a JSON stdout object with `saved_to`. It writes under `$PPLX_OUTPUT_DIR`, then `$RD`, then the current directory. Never suppress stderr in `bash()` calls; do not redirect `2>/dev/null`, because it hides SDK/auth/fetch errors. Always quote every URL passed inside shell snippets.

One-off result shapes:

- List-returning SDK calls print `{results:[...], total, saved_to}`.
- `pplx_sdk.search.web(...)` results have `{url, title, domain, snippet?, summary?, date?}`.
- `pplx_sdk.search.academic(...)` results have `{url, title, abstract?, doi?, authors?, published_date?}`; use `abstract`, not `summary` or `content`.
- `pplx_sdk.search.images(...)` results have `{url, title, thumbnail_url, width?, height?, source?}`; there is no text-summary field.
- `pplx_sdk.search.shopping(...)` results have `{title, vendor, url, rating?, reviews_count?, images, offers, vendor_info?, attributes?, reviews?, options?}`; there is no text-summary field.
- `pplx_sdk.search.videos(...)` results have `{url, title, snippet, source?, channel?, duration?}`.
- `pplx_sdk.search.people(...)` results have `{url, title, summary?}`; use only for actual people/professionals, not companies, products, jobs, or reviews.
- `pplx_sdk.content.fetch(...)` results have `{url, title?, description?, author?, hostname?, published_date?, is_paywall, is_cached, content?, error?}`. Always read `content`; on fetch failure `error` is set.
- `pplx_sdk.content.snippets(...)` results have `{url, text?, tokens_count?, error?}`; use `text`, not `content` or `summary`.

## Routing

### SDK Reference

- **Choose an index** - `pplx` provides the main `web` index plus specialized indexes such as `people`; see `reference/search.md` for the full list and details on how to use them.
- **Fetch content for URLs** - `content` provides full page fetches, query-focused snippets, and structured profile enrichment; see `reference/content.md` for details and examples.
- **Use LLM to postprocess results** - `llm` provides a flexible interface to run LLM extraction and transformation on search results and content; see `reference/llm.md` for details and examples.
- **Access low-level async API** - use `reference/async.md` for asynchronous version of the SDK & examples.

### Common Patterns

- **Send parallel independent requests** - use `patterns/fanout.md` for multiple search queries, URL fetches, or LLM extraction calls.
- **Build a multi-step pipeline** - use `patterns/multi-step.md` for JSONL artifacts and script discipline.
- **Long-running tasks** - use `patterns/checkpoint.md` when any step risks exceeding the `bash()` window or should persist intermediate results for debugging or reuse.

## Recipes

This skill includes recipes for specialized workflows:

- **People research** - Find people matching criteria for sourcing, alumni, experts, investors/partners, or named-person checks; see `recipes/people-research.md`.