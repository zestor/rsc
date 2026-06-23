# LLM Reference

Use `pplx_sdk.llm` to postprocess search results and fetched content with structured extraction. Keep identity fields such as `url` in the input row, not in the schema.

## Single Extract Call

```python
import json
import pplx_sdk

INSTRUCTION = """Decide if each record is relevant to the user's research question."""
SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["matches"],
}

results = pplx_sdk.llm.extract(
    items=[json.dumps(row) for row in rows],
    instruction=INSTRUCTION,
    output_schema=SCHEMA,
    max_tokens=16384,
)

for row, result in zip(rows, results, strict=True):
    if result.error:
        continue
    if result.result.get("matches"):
        keep(row)
```

Returns `list[ExtractResult]` aligned 1:1 by position with `items`. Each result has `.result` (schema-shaped dict on success, `None` on error) and `.error` (`ExtractError` on failure, `None` on success).

## Larger Pools

For larger pools, use `pplx_sdk.llm.extract_many` and `pplx_sdk.utils.get_extract_matches(raw_results)`. `extract_many` chunks `items` internally and dispatches chunks concurrently. See `patterns/fanout.md` for the quick pattern and `patterns/checkpoint.md` when work must survive timeout or resume.

Sizing:

- Each item costs about 2-10s with high variance.
- Up to about 80 items: one `pplx_sdk.llm.extract` call is usually comfortable inside the 300s `bash()` ceiling.
- Anything larger, or anything that should survive timeout via re-run: use `patterns/checkpoint.md`.

## Rules

- **Single-call `llm.extract` is 1:1 by position.** Recover input metadata by zipping with the original row list.
- **Default `max_tokens=16384` for classifier schemas.** Raise to 32768, then 65536, only for persistent `code == "max_tokens"` errors.
- **Keep identity outside the schema.** Carry `url` in the input row; fanout helpers preserve call provenance in `FanoutResult.spec`.
- **Never write an automated retry loop.** Schema and persistent token-budget failures do not recover from blind re-runs; fix the schema, instruction, or `max_tokens`, then rerun.
- **No empty-string `enum` values.** `""` in an `enum` is rejected by some providers (Gemini). Use a non-empty sentinel (`"unknown"`, `"none"`) or mark the field optional / nullable instead; map to blank only at final CSV/export time.
- **No boolean JSON Schema shortcuts under `properties`.** `"field": true` / `"field": false` is legal JSON Schema but doesn't survive conversion for some providers (Gemini). Use an explicit subschema like `{"type": "boolean"}`, or omit the field / mark it optional.

## Error Shapes

`ExtractResult.error` is an `ExtractError(code, message, retryable)` with codes such as `auth`, `config`, `connect`, `invalid_schema`, `max_tokens`, `response_decode`, `server`, `tls`, and `transport`.

When using `get_extract_matches`, errors are returned as failed `FanoutResult` envelopes. Schema-shape problems such as missing or non-boolean `matches` are wrapper `ValueError`s, not `ExtractError`s, so inspect the payload before grouping by `error.code`.
