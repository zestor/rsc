# Async Reference

Use the sync facade (`pplx_sdk.search.*`, `pplx_sdk.content.*`, `pplx_sdk.llm.*`) by default. It handles event-loop and client lifecycle internally.

Drop to async clients only when you need:

- A custom concurrency model that `_many` / `fanout` defaults do not cover.
- Long-running concurrent state across multiple SDK calls inside one coroutine.
- Direct use of `pplx_sdk.utils.fanout()` with your own async function.

```python
from pplx_sdk import AsyncPplxClient

async with AsyncPplxClient() as client:
    hits = await client.search.web("python release notes", limit=10)
```

`AsyncPplxClient` is an async context manager. Reuse one client per script; do not construct one client per coroutine inside `asyncio.gather`, because that pattern leaks connections.

`AsyncLlmApiClient` is not a context manager; instantiate it plainly:

```python
from pplx_sdk import AsyncLlmApiClient

llm = AsyncLlmApiClient()
results = await llm.extract(
    items=items,
    instruction=INSTRUCTION,
    output_schema=SCHEMA,
    max_tokens=16384,
)
```

For bounded concurrent dispatch with per-call error isolation, use `pplx_sdk.utils.fanout()`. See `patterns/checkpoint.md` for a concrete composed example.
