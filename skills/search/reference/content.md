# Content Reference

Use `pplx_sdk.content` after search when you need more than a hit title or summary.

## Full Page Fetch - `content.fetch`

Fetch full page content for URLs. Use `cache_enabled=False` when freshness matters.

Simple:

```python
save_and_print(pplx_sdk.content.fetch(["https://example.com"]))
```

With options:

```python
save_and_print(pplx_sdk.content.fetch(
    ["https://example.com/a", "https://example.com/b"],
    cache_enabled=False,
))
```

`PageResult` fields: `url`, `title`, `content`, `hostname`, `is_paywall`, `is_cached`, `error`.

Use `fetch` for a small single request. Use `fetch_many` for arbitrary-size URL pools; it auto-chunks and returns one `FanoutResult` per input URL. See `patterns/fanout.md`.

## Structured Profile Fetch - `content.fetch_people`

Fetch fielded people/profile data from profile URLs. Use this before LLM filtering when criteria can be expressed against company history, education, skills, location, or current role.

Simple:

```python
save_and_print(pplx_sdk.content.fetch_people(["https://example.com/profile"]))
```

From search hits:

```python
save_and_print(pplx_sdk.content.fetch_people([hit.url for hit in deduped[:50]]))
```

`PeopleFetchResult` fields: `url`, `full_name`, `people_headline`, `location`, `country`, `current_companies`, `previous_companies`, `education_ongoing`, `education_finished`, `skills`, `error`.

Accepts 1-50 URLs per call. Order is preserved. URLs the crawler cannot parse as profiles return `error: "not found"` while other entries succeed independently. Loop in chunks of 50 for larger pools.

## Query-Focused Snippets - `content.snippets`

Use snippets when search summaries do not disambiguate a specific claim, or when you need a focused excerpt from known URLs.

Simple:

```python
save_and_print(pplx_sdk.content.snippets(
    query="specific expertise query",
    urls=["https://example.com/profile"],
))
```

Multiple URLs:

```python
save_and_print(pplx_sdk.content.snippets(
    query="specific expertise query",
    urls=urls[:20],
))
```

`SnippetResult` fields: `url`, `text`, `tokens_count`, `error`.

## When To Use Each

- Use `content.fetch` / `fetch_many` for full page text, dossier extraction, or page-level evidence.
- Use `content.fetch_people` for people/profile enrichment before filtering.
- Use `content.snippets` for targeted evidence from known URLs without fetching full pages.
