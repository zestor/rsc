# Search Reference

Use `pplx_sdk.search` to query Perplexity indexes. Prefer short keyword phrases, usually 3-7 meaningful tokens. Do not use boolean syntax; `AND`, `OR`, and `NOT` are treated as literal words.

## Indexes

### Web - `pplx_sdk.search.web`

General-purpose public web search. Use when the answer is likely on public pages, docs, articles, blogs, company pages, forums, or social pages.

**Hit fields:** `url`, `title`, `domain`, `snippet?`, `summary?`, `date?`.

**Filters:** `limit`, `country`, `domains`, `excluded_domains`.

Simple:

```python
save_and_print(pplx_sdk.search.web("python 3.13 release notes"))
```

With filters:

```python
save_and_print(pplx_sdk.search.web(
    "python 3.13 release notes",
    limit=10,
    domains=["docs.python.org"],
    excluded_domains=["dev.to"],
    country="US",
))
```

### People - `pplx_sdk.search.people`

Profile search, strongest for intersection queries such as `company x role` or `role x company x location` ("senior PM fintech London"). Use only for people or professionals, not companies, jobs, products, reviews, or business listings.

**Hit fields:** `url`, `title`, `summary?`.

**Filters:** `limit`, `country`, `name`, `company`, `skills`, `location`, `education`. `country` is a top-level region filter (ISO country code); `location` token-searches the profile location field.

Simple:

```python
save_and_print(pplx_sdk.search.people("product manager fintech London"))
```

With filters:

```python
save_and_print(pplx_sdk.search.people(
    "product manager fintech London",
    limit=50,
    company="Stripe",
    location="London",
    skills="fintech payments",
))
```

## Many Queries

For multiple query variants against the same index, use the `_many` helpers

```python
raw_results = pplx_sdk.search.web_many(
    [
        {"query": "python 3.13 release notes"},
        {"query": "python 3.13 whats new", "domains": ["docs.python.org"]},
    ],
    limit_per_query=10,
)
```

See `patterns/fanout.md`.
