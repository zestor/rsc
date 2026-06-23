# Resumable pipelines

Use checkpointed pipelines when the input row count exceeds what fits in a single `bash()` 300s window: bulk URL fetch (200+ URLs), people enrichment over large pools, LLM classification or structured extraction over many rows, dossier extraction. The shared survival mechanic is **persist work per batch, skip already-done batches on re-run** with `pplx_sdk.utils.Checkpoint` plus `pplx_sdk.utils.fanout`.

Reach for this when the input pool is large enough to risk a `bash()` timeout (see `reference/llm.md` → Larger Pools), or when re-runs need to skip already-completed work after a SIGKILL or timeout. For small pools that fit in one call, use the single-call SDK methods directly (see `reference/search.md`, `reference/content.md`, and `reference/llm.md`).

## The helper: `Checkpoint`

Use `pplx_sdk.utils.Checkpoint(workspace)`. It answers one question: **"have I done this work? If yes, skip. If no, do it and remember I did."**

Surface:

- `has(key) -> bool` — fragment file exists?
- `record(key, rows) -> int` — atomic JSONL write. Idempotent: a duplicate `record(key, ...)` overwrites the fragment.
- `read_all() -> Iterator[dict]` — yield rows from every fragment in completion order (mtime sort).

Keys must be file names, not paths. `record("../escape", rows)` raises `ValueError`; `has("../escape")` returns `False`.

Storage layout under `workspace/`:

```
workspace/
└── fragments/
    └── {key}.jsonl       one file per recorded key, JSONL rows
```

**One `Checkpoint` per pipeline step.** Use a step-scoped subdir (e.g. `pplx_sdk.utils.Checkpoint(RD / "filter")`, `pplx_sdk.utils.Checkpoint(RD / "dossier")`) so `read_all()` from one step never sees fragments produced by another. Sharing `Checkpoint(RD)` across steps means filter fragments leak into the dossier reader and vice versa.

## Composing with `fanout`: the batched filter pattern

The canonical use — classify a pool larger than fits in one `bash()` window (above ~80 rows, see `reference/llm.md` → Larger Pools) for match / no-match against criteria. Compose `Checkpoint` (persistence) + `pplx_sdk.utils.fanout` (bounded concurrent dispatch) + your per-batch operation.

```python
import asyncio
import hashlib
import json
import os
from pathlib import Path

from pplx_sdk import AsyncLlmApiClient
from pplx_sdk.utils import Checkpoint, fanout, read_jsonl, write_jsonl

INSTRUCTION = """Decide if each candidate matches: <criteria>.
Phrase exclusions: drop if NOT <X>, NOT <Y>, NOT <Z>."""

SCHEMA = {
    "type": "object",
    "properties": {"matches": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["matches"],
}

BATCH = 10
CONCURRENCY = 3
MAX_TOKENS = 16384

RD = Path(os.environ["RD"])
INPUT_FILE_NAME = RD / "enriched.jsonl"
MATCHES_FILE_NAME = RD / "matches.jsonl"
ERRORS_FILE_NAME = RD / "errors.jsonl"

rows = read_jsonl(INPUT_FILE_NAME)
ck = Checkpoint(RD / "filter")
llm = AsyncLlmApiClient()


def _digest(payload):
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:8]


# 1. Config digest. Same INSTRUCTION/SCHEMA/MAX_TOKENS -> reuse fragments; change any -> fresh keys -> fresh work.
config = _digest([INSTRUCTION, SCHEMA, MAX_TOKENS])

# 2. Build a key per batch. Same rows + same config -> same key -> fragment already on disk -> skip on re-run.
batches = []
for i in range(0, len(rows), BATCH):
    batch = rows[i : i + BATCH]
    batches.append({"key": f"{config}:{_digest(batch)}", "batch": batch})

pending = [b for b in batches if not ck.has(b["key"])]


# 3. Per-batch operation. `r` here is an `ExtractResult` (not a `FanoutResult`) because
#    `llm.extract` returns `list[ExtractResult]`; `r.error` is the per-item LLM error.
async def process(*, key, batch):
    items = [json.dumps(r) for r in batch]
    results = await llm.extract(
        items=items,
        instruction=INSTRUCTION,
        output_schema=SCHEMA,
        max_tokens=MAX_TOKENS,
    )
    out = []
    for row, r in zip(batch, results, strict=True):
        if r.error is not None:
            out.append({**row, "url": row["url"], "ok": False, "error": r.error.to_dict()})
        else:
            extracted = r.result or {}
            out.append({**row, **extracted, "url": row["url"], "ok": True})
    ck.record(key, out)


async def main():
    # 4. Concurrent dispatch with per-call error isolation, courtesy of fanout.
    await fanout(process, pending, concurrency=CONCURRENCY)


asyncio.run(main())

# 5. Flat read — no dedupe here; the *Producing flat outputs* section below handles re-run duplicates.
matches, errors = [], []
for row in ck.read_all():
    if not row["ok"]:
        errors.append(row)
        continue
    if row.get("matches"):
        matches.append(row)

write_jsonl(MATCHES_FILE_NAME, matches)
write_jsonl(ERRORS_FILE_NAME, errors)
print(f"{MATCHES_FILE_NAME}\nfilter: {len(matches)} matches, {len(errors)} errors")
```

Filter-specific notes:

- **Phrase as exclusions.** "Drop if not X" produces fewer false positives than "Include only X".
- **`url` belongs in the row, not the schema.** Preserve the source row and merge identity last: `{**row, **extracted, "url": row["url"]}`. Full row-layout rule: `patterns/multi-step.md` → Row Layout.
- **`max_tokens` defaults and escalation tiers** live in `reference/llm.md` → Rules. Apply the same escalation here.

## Handling extract errors

Group failed rows by `error.code` when present; for wrapper errors without a code (for example schema-shape `ValueError`s from `get_extract_matches`), group by error type/message instead:

- **`max_tokens`** (and `response_decode`) — slim the row set to prior errors before re-running, because raising `MAX_TOKENS` changes every config-digest key (a full rerun would re-process successes too). Because error rows preserve the source fields, build retry rows from failed fragments after dropping checkpoint-only fields (`ok`, `error`). The *Producing flat outputs (resolved-on-retry)* section merges old + new fragments by URL. Escalation tiers and the schema-too-rich fallback live in `reference/llm.md` → Rules.

```python
retry_rows = [
    {k: v for k, v in r.items() if k not in {"ok", "error"}}
    for r in ck.read_all()
    if not r["ok"]
]
```

- **Schema validation errors** — fix the schema or instruction; the rows themselves are fine. Re-running unchanged won't help.
- **Transient** (`timeout`, `connect`, `5xx`, `retryable=True`) — re-run as-is; `Checkpoint` skips completed batches. `retryable=True` is the SDK's hint that the call is worth re-running unchanged.
- **Anything else** — sample one row, read `error.message`, decide.

See `reference/llm.md` → Rules for the canonical statement on why automated retry loops are off-limits.

## Other pipelines that fit

`Checkpoint` is agnostic to what's stored under each key. Swap the per-batch operation:

| Pipeline | What `process` does | What's in the row | `config_digest` inputs |
| --- | --- | --- | --- |
| Bulk URL fetch | `pplx_sdk.content.fetch_many(urls=...)` | `{"url", "ok", "content", "error?"}` | fetch options (e.g. `cache_enabled`) |
| Bulk people enrichment | `pplx_sdk.content.fetch_people(urls=...)` | `{"url", ...profile fields}` | — |
| Bulk snippet extraction with fixed query | `pplx_sdk.content.snippets(query=QUERY, urls=...)` | `{"url", "text", ...}` | `QUERY` |
| Dossier extraction | `fetch_many` then `extract_many` chained | `{"url", "dossier": {...}}` | `INSTRUCTION`, `SCHEMA`, `max_tokens` |
| Single expensive operation (caching pattern) | one async call, one row | whatever it returns | the call's params |

## Rules

- **Defaults `BATCH=10, CONCURRENCY=3`.** Empirically reliable — no per-call rate-limit hits, finishes ~120 rows under the 300s `bash()` ceiling. Larger batches and higher concurrency lose more on timeout and trigger upstream rate limits.
- **Put the identity field (typically `url`) on every row** persisted under a key. Downstream filters (resolved-on-retry dedup, error grouping) read it from the row.
- **Config digest covers every input that affects what success / error means** — instruction strings, schemas, `max_tokens`, the fixed query for snippets. Missing an input means changing it doesn't change the key and old fragments contaminate the read.
- **The checkpoint handles latency; keyword filters don't.** Don't sidestep `bash()` timeouts with regex or keyword pre-/post-filters (see `patterns/fanout.md` → Pattern for the canonical statement).

## Re-run semantics

Same inputs (`INSTRUCTION`, `SCHEMA`, `MAX_TOKENS`, the row set): re-run is a no-op. All fragments are on disk, `pending` is empty.

Different rows, same config: new batches run fresh, but the previously-stored fragments stay on disk and `read_all()` will still yield them — they'll pollute the flattened outputs. Delete the step's checkpoint subdir (e.g. `$RD/filter/`) when changing the row set.

Different config (changed instruction, schema, max_tokens) **with the same row set**: config digest changes → all batch keys change → `has()` returns False for all → full rerun, which can be expensive. To raise `MAX_TOKENS` for *only* the prior errors (the common retry case), slim the row set first — see *Handling extract errors → `max_tokens`* above. Old fragments stay on disk under their old keys; `read_all()` reads them too, and the *Producing flat outputs* filter merges old + new via URL.

## Producing flat outputs (resolved-on-retry)

If you re-run with a higher `max_tokens` to drain `max_tokens` errors, those rows succeed under new keys while their old error rows are still in `read_all()` output. The "resolved-on-retry" filter drops any error whose URL succeeded in a later batch — that's the rebuild step the canonical recipe ends with. Write it once at the end of the script:

```python
succeeded_urls = {r["url"] for r in ck.read_all() if r["ok"]}

matches, errors = [], []
for r in ck.read_all():
    if r["ok"] and r.get("matches"):
        matches.append(r)
    elif not r["ok"] and r["url"] not in succeeded_urls:
        errors.append(r)

write_jsonl(RD / "matches.jsonl", matches)
write_jsonl(RD / "errors.jsonl", errors)
```

`$RD/matches.jsonl` and `$RD/errors.jsonl` are then the canonical flat files downstream steps (e.g. dossier enrichment in `recipes/people-research.md`) load. Per-batch fragments under `$RD/<step>/fragments/` retain the full history for forensics, including resolved-on-retry errors.
