# Multi-Step Pipelines

Use this pattern when a search task needs multiple scripted steps and reusable artifacts, but each step still fits inside one `bash()` window. If a step may exceed the 300s window or must resume after timeout, use `patterns/checkpoint.md`.

## Script Discipline

- **Write scripts to disk, not heredoc.** Save Python to `$RD/scripts/NN_step.py` (for example `01_search.py`, `02_enrich.py`) and run it with `api_credentials=["pplx-sdk"]`.
- **Iterate via `apply_patch`, not full rewrites.** A small patch surfaces exactly what changed.
- **Keep the workflow in scripts.** Once this skill is loaded for a task, keep search, fetch, and extract work in the saved scripts.
- **Use one `RD` per task.** Put scripts in `$RD/scripts/`; write outputs under `$RD`. Shared `RD` paths make subagents collide on intermediate files.
- **End every script by printing the output file name, then a summary.** Example: `print(f"{OUTPUT_FILE_NAME}\nsearch: {len(rows)} rows")`.

```python
bash(
    command="python3 $RD/scripts/01_search.py",
    api_credentials=["pplx-sdk"],
)
```

## JSONL Artifacts

Use JSONL, never JSON arrays. One object per line keeps partial outputs readable and reusable.

```python
import pplx_sdk

TIMESTAMP = pplx_sdk.utils.now_timestamp()
OUTPUT_FILE_NAME = pplx_sdk.utils.output_file_name("web_search", "results", timestamp=TIMESTAMP)

rows = [
    {"url": "https://example.com/a", "title": "Example A"},
    {"url": "https://example.com/b", "title": "Example B"},
]
pplx_sdk.utils.write_jsonl(OUTPUT_FILE_NAME, rows)
print(f"{OUTPUT_FILE_NAME}\nweb_search: {len(rows)} rows")
pplx_sdk.utils.print_preview_jsonl(OUTPUT_FILE_NAME, limit=5, max_chars=500)
```

Use `read_jsonl` when the next step needs saved rows back in memory:

```python
rows = pplx_sdk.utils.read_jsonl(OUTPUT_FILE_NAME, limit=None)
```

## Fanout Artifacts

When a step uses a `_many` helper, keep successful rows and errors separate. Skipping errors hides failed queries, fetches, or extraction chunks.

```python
raw_results = pplx_sdk.search.web_many(QUERIES, limit_per_query=10)
results, errors = pplx_sdk.utils.partition(raw_results, lambda result: result.ok)
rows = pplx_sdk.utils.flatten_fanout_rows(results)
deduped_rows = pplx_sdk.utils.dedup_by_url(rows)

pplx_sdk.utils.write_jsonl(OUTPUT_FILE_NAME, deduped_rows)
pplx_sdk.utils.write_jsonl(ERROR_OUTPUT_FILE_NAME, errors)
pplx_sdk.utils.print_preview_jsonl(OUTPUT_FILE_NAME, limit=5, max_chars=500)
```

For search/fetch, `flatten_fanout_rows(results)` emits one row per hit/page and preserves request provenance under `row["spec"]`. Use `row["spec"]["query"]`, `row["spec"]["domains"]`, etc.; do not expect top-level `row["query"]`.

## Preview Rule

After writing a JSONL artifact, inspect it with `pplx_sdk.utils.print_preview_jsonl(path, limit=5)`. If fields are truncated, increase `max_chars` instead of printing raw `json.dumps(...)` loops. Run the preview before custom projection so the actual row shape is visible.

## Dedup

`pplx_sdk.utils.dedup_by_url(hits)` and `pplx_sdk.utils.dedup_by_field(hits, field)` handle dicts and typed SDK hits uniformly. They are first-occurrence-wins.

For flattened search rows, longest summary is often most useful:

```python
deduped = pplx_sdk.utils.dedup_by_url(
    sorted(merged_hits, key=lambda row: len(row.get("summary") or ""), reverse=True)
)
```

## Row Layout

- **Stable identity:** keep `url` on every downstream row.
- **Thin classifier schemas** (`{matches, reason}`): preserve source row, merge classifier fields, then put `url` last so schema output cannot clobber identity: `{**row, **result, "url": row["url"]}`.
- **Richer extractions** (dossiers, profiles): nest structured output under `extract`: `{"url": row["url"], "spec": spec, "extract": result}`.

Keep intermediate files even when later steps fail. Partial outputs help debugging and resume.
