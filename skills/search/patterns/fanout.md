# Fan-Out

Use `_many` helpers to send many parallel SDK requests without managing concurrency yourself.

Each `_many` helper returns one `FanoutResult` per input query/item/URL. `extract_many` returns one `FanoutResult[ExtractResult]` per input item.

## Available Helpers

- `pplx_sdk.search.web_many(queries, limit_per_query=..., concurrency=...)`
- `pplx_sdk.search.people_many(queries, limit_per_query=..., concurrency=...)`
- `pplx_sdk.content.fetch_many(urls, chunk_size=10, concurrency=..., ...)`
- `pplx_sdk.llm.extract_many(items, instruction=..., output_schema=..., chunk_size=10, concurrency=..., max_tokens=16384)`

Defaults: `concurrency=5`; `fetch_many` / `extract_many` use `chunk_size=10`; `extract_many` defaults to `max_tokens=16384`.

## Web Search

Simple query variants:

```python
save_and_print(pplx_sdk.search.web_many(
    [
        "python 3.13 release notes",
        "python 3.13 whats new",
    ],
    limit_per_query=5,
))
```

Per-query kwargs:

```python
save_and_print(pplx_sdk.search.web_many(
    [
        {"query": "python 3.13 release notes"},
        {"query": "python 3.13 whats new", "domains": ["docs.python.org"]},
    ],
    limit_per_query=10,
    concurrency=5,
))
```

`web_many` and `people_many` accept either query strings or kwargs dicts forwarded to the single-call method. Prefer `limit_per_query` at the `_many` call site because `limit` is per query, not a batch-wide cap.

## Content Fetch

```python
save_and_print(pplx_sdk.content.fetch_many(
    [
        "https://example.com/a",
        "https://example.com/b",
    ],
    cache_enabled=False,
))
```

`fetch_many` accepts a flat list of URL strings. It auto-chunks past the upstream per-call cap and returns one `FanoutResult` per input URL, so `output[i]` corresponds to `urls[i]`.

## LLM Extract

```python
ROWS = [
    {"url": "https://example.com/a", "title": "Example A", "content": "..."},
    {"url": "https://example.com/b", "title": "Example B", "content": "..."},
]

INSTRUCTION = """Decide if each record is relevant.
Return matches=true only when the record contains useful evidence."""

SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["matches"],
}

save_and_print(pplx_sdk.llm.extract_many(
    items=ROWS,
    instruction=INSTRUCTION,
    output_schema=SCHEMA,
))
```

For classifier schemas with boolean `matches`, `pplx_sdk.utils.get_extract_matches(raw_results)` can collect matching rows and error envelopes. Use a custom loop over raw results when downstream code needs flat classifier rows or structured `ExtractError.code`.

## Result Shape

Each `_many` result is a `FanoutResult`:

- `result.ok` - true when the call/chunk succeeded.
- `result.spec` - the request provenance for that result.
- `result.result` - the SDK result on success.
- `result.error` - the isolated exception on fanout-level failure.

For artifact-producing workflows, split successes and errors, flatten rows, write JSONL, and preview output as described in `patterns/multi-step.md`.

## Custom Async Fan-Out

If you need more complex logic with explicit async control, see `reference/async.md`
