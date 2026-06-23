# People Search

The agent runs this pipeline as Python scripts that `import pplx_sdk`. Every step — search, content fetch, snippets, LLM extraction — is an SDK method call from inside an async script the agent **writes to a `.py` file** and runs with `python3 script.py` from a `bash()` tool call. **Never pipe Python via heredoc** (`python3 - <<'PY' ... PY`) — heredoc code is invisible in the transcript, can't be re-run with a tweak, and tracebacks point at `<stdin>` instead of a file:line. Use `jq` only for ad-hoc inspection; data manipulation lives in Python.

## Setup

The SDK auto-loads creds from `PPLX_SDK_API_KEY` and `PPLX_SDK_BASE_URL`. **Pass `api_credentials=["pplx-sdk"]` on every `bash()` call that runs a Python script using the SDK.** Without it, `AsyncPplxClient()` and `AsyncLlmApiClient()` raise `AuthenticationError` at construction.

Do not hardcode keys or call `os.environ[...] = ...` in scripts — let the bash tool's credential injection handle it.

## Tool Selection

`client.search.people` queries a profile index — strong recall for keyword-matchable profiles (company intersections, role+company+location), weak on niche domains, senior executives without standard profiles, and criteria the index can't express (language spoken, tenure length, "currently" vs "formerly").

Supplement with `client.search.web` when:
- The query targets a specific organization's team/about page (VC partner lists, lab group pages, C-suite rosters)
- Criteria need temporal awareness ("currently at X", "left Y in 2024")
- The domain is niche academic (specific lab, conference community, thesis topic)
- `client.search.people` returns many results but few true matches after filtering

For comprehensive searches, run both in parallel and merge.

## API surface

`AsyncPplxClient` is an async context manager — always wrap its use in `async with`. **`AsyncLlmApiClient` is NOT a context manager** — instantiate it plainly and call `.extract` directly. `async with AsyncLlmApiClient() as llm:` raises `TypeError`.

Hits and pages from `AsyncPplxClient` are SDK objects — call `.to_dict()` on each to materialize as JSON-serializable dicts before writing to disk.

### client.search.people

```python
import asyncio, json
from pplx_sdk import AsyncPplxClient

async def main():
    async with AsyncPplxClient() as client:
        res = await client.search.people("product manager fintech London", limit=50)
        for h in res:
            print(json.dumps(h.to_dict()))

asyncio.run(main())
```

Each hit dict has `title`, `url`, `summary`. Default `limit=10`; use 50 for broad searches, 100 for exploratory or critical searches (max 100). Named lookups can use 10.

Queries are natural language, not boolean. AND/OR/NOT are literal words. Typos auto-corrected.

Keep queries to ~5–7 meaningful tokens. At 8+ tokens the index can't match all terms — split criteria across multiple shorter queries.

**Vary queries.** A single query misses ~20% of relevant people. Run 3+ parallel queries varying:
- Role titles + acronyms ("PM" / "product manager" / "product lead")
- Company name forms ("a16z" / "Andreessen Horowitz", "HPE" / "Hewlett Packard Enterprise")
- Industry terms ("ISV" / "independent software vendor")
- Scope slicing (team, geography, seniority)

Skip the acronym/expansion pairing only when the acronym is the dominant brand (IBM, SAP).

Fan out queries on a single client with `asyncio.gather`:

```python
async with AsyncPplxClient() as client:
    queries = [
        "senior PM Google Cloud",
        "Google Maps product lead",
        "Google AI product manager",
    ]
    results = await asyncio.gather(*(client.search.people(q, limit=50) for q in queries))
    rows = []
    for q, res in zip(queries, results):
        for h in res:
            d = h.to_dict()
            d["query"] = q
            rows.append(d)
```

For more than ~8 concurrent queries, bound with `asyncio.Semaphore` to avoid upstream rate limits.

#### Field filters

**Filters are a supplement to plain-text search, not a replacement.** Always run plain-text `client.search.people(query, ...)` queries first — they have the broadest recall. Add filtered queries on top *as additional fan-out variants* when a structural criterion (company, location, alumni status) would help narrow the result set. Never replace a plain-text query with a filtered-only query — filtered queries hit a narrower index slice and miss profiles the plain-text search would find.

`client.search.people` accepts keyword-only filter kwargs that scope results to people whose profile fields match all of the provided tokens. Each filter is a space-separated keyword string; tokens are split on whitespace and ANDed as `contains` clauses against the target field(s) — `company="Google Maps"` requires both `"Google"` and `"Maps"` to appear, not the literal phrase.

| Kwarg | Matches against |
|---|---|
| `name=` | full name |
| `company=` | current OR previous companies (fans out) |
| `skills=` | skills |
| `location=` | location OR country (fans out) |
| `education=` | finished OR ongoing education institutions (fans out) |

Filters are strict — non-matching profiles are excluded, not just downranked. Free-text `query` is still the primary ranking signal; use filters to scope, not to rank.

Pattern: fan filters out alongside the plain-text query rather than instead of it. Each filtered variant becomes one more entry in the parallel `client.search.people` calls, dedup'd by URL after merge:

```python
async with AsyncPplxClient() as client:
    # Always include the plain-text variants — they have the broadest recall.
    variants = [
        {"query": "senior ML engineer NVIDIA San Francisco"},
        {"query": "machine learning engineer NVIDIA Bay Area"},
        # Add filtered variants as supplements, not replacements:
        {"query": "senior ML engineer", "company": "NVIDIA", "location": "San Francisco"},
        {"query": "machine learning engineer", "company": "NVIDIA"},
    ]
    results = await asyncio.gather(
        *(client.search.people(limit=50, **v) for v in variants)
    )
```

When to add a filter alongside (not instead of) the plain-text query:

- **Add a filter** when the criterion is structural (company affiliation, location, alumni status) AND the plain-text query alone is returning too much noise. Filters scope crisply and don't compete with the ranker.
- **Keep it in the query only** when the criterion is semantic ("senior", "fintech", "AI safety") — the ranker handles fuzzy matches the filter index can't, and filters won't help.

### Deduplication

Dedup the merged hits by URL keeping the longest summary (pure Python, no jq):

```python
def dedup(hits):
    by_url = {}
    for h in hits:
        url = h.get("url")
        if not url:
            continue
        prev = by_url.get(url)
        if prev is None or len(h.get("summary") or "") > len(prev.get("summary") or ""):
            by_url[url] = {"url": url, "title": h.get("title"), "summary": h.get("summary")}
    return list(by_url.values())
```

### AsyncLlmApiClient.extract (filtering)

Classifies items against criteria. Takes:
- `items` — list of strings (one row per record). Pass JSON-encoded dicts when the model needs structured input.
- `instruction` — the criteria prompt.
- `output_schema` — JSON Schema dict.

Returns an extract response whose body is a sequence of result entries aligned **1:1 by position** with `items`. Each entry has `result` (schema-shaped dict on success, `None` on error) and `error` (truthy only on failure). The wrapper varies between SDK builds — sometimes a top-level wrapper with `.to_dict()`, sometimes a list of `ExtractResult` objects. Materialize to plain dicts before iterating:

```python
raw = resp.to_dict()["results"] if hasattr(resp, "to_dict") else list(resp)
results = [r if isinstance(r, dict) else r.to_dict() for r in raw]
```

Each `results[i]` is now a dict — use `r.get("result")` and `r.get("error")`.

Each item costs ~2–10s with high variance and `bash()` caps a single call at 300s. Size by pool: ≤80 in one call, 80–300 use the resumable recipe below (re-run on `bash()` timeout — completed batch keys in the manifest are skipped), 300+ split across separate `bash()` calls keyed by pool slice. Append per batch to disk so partial work survives:

```python
import asyncio, hashlib, json
from pathlib import Path
from pplx_sdk import AsyncLlmApiClient

INSTRUCTION = """Decide if each candidate matches: senior PM at a fintech in London.
Anchor on the candidate's `summary`. Phrase exclusions: drop if NOT a senior PM,
NOT at a fintech, or NOT London-based."""

SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["matches"],
}

BATCH = 10
CONCURRENCY = 3
MAX_TOKENS = 16384  # measured floor for filter schemas; raise to 32768/65536 only on persistent max_tokens errors

def _normalize_error(err):
    if err is None:
        return None
    if isinstance(err, dict):
        return {"code": err.get("code"), "message": err.get("message") or str(err)}
    return {"code": getattr(err, "code", None),
            "message": getattr(err, "message", None) or str(err)}

def _digest(payload):
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:8]

async def filter_rows(rows, rd, max_tokens=MAX_TOKENS):
    rd = Path(rd)
    batch_dir = rd / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    manifest = rd / "filter_manifest.txt"
    done = set(manifest.read_text().split()) if manifest.exists() else set()
    config = _digest([INSTRUCTION, SCHEMA, max_tokens])  # changes invalidate keys
    llm = AsyncLlmApiClient()
    sem = asyncio.Semaphore(CONCURRENCY)
    batches = [(f"{config}:{_digest(b)}", b)
               for b in (rows[i:i+BATCH] for i in range(0, len(rows), BATCH))]
    pending = [(k, b) for k, b in batches if k not in done]

    async def run_batch(key, batch):
        async with sem:
            items = [json.dumps(r) for r in batch]
            resp = await llm.extract(items=items, instruction=INSTRUCTION,
                                     output_schema=SCHEMA, max_tokens=max_tokens)
            raw = resp.to_dict()["results"] if hasattr(resp, "to_dict") else list(resp)
            results = [r if isinstance(r, dict) else r.to_dict() for r in raw]
            mlines, elines = [], []
            for row, r in zip(batch, results):
                err = _normalize_error(r.get("error"))
                if err:
                    elines.append(json.dumps({"row": row, "error": err,
                                              "max_tokens": max_tokens, "batch_key": key}))
                    continue
                result = r.get("result") or {}
                if result.get("matches"):
                    mlines.append(json.dumps({**result, "url": row.get("url")}))
            # Per-batch files: truncating write → re-running a batch overwrites cleanly.
            (batch_dir / f"matches.{key}.jsonl").write_text("".join(l + "\n" for l in mlines))
            (batch_dir / f"errors.{key}.jsonl").write_text("".join(l + "\n" for l in elines))
            with manifest.open("a") as f:
                f.write(f"{key}\n")

    await asyncio.gather(*(run_batch(k, b) for k, b in pending))

    # Rebuild flat outputs in two passes: (1) emit matches and collect succeeded urls,
    # (2) emit only errors whose url did not succeed in any later batch (resolved-on-retry
    # rows stay in the per-batch fragments but are filtered out of the flat error view).
    keys = manifest.read_text().split() if manifest.exists() else []
    succeeded = set()
    with (rd / "matches.jsonl").open("w") as mf:
        for key in keys:
            mp = batch_dir / f"matches.{key}.jsonl"
            if not mp.exists():
                continue
            text = mp.read_text()
            mf.write(text)
            for line in text.splitlines():
                try:
                    succeeded.add(json.loads(line)["url"])
                except (json.JSONDecodeError, KeyError):
                    pass
    with (rd / "extract_errors.jsonl").open("w") as ef:
        for key in keys:
            ep = batch_dir / f"errors.{key}.jsonl"
            if not ep.exists():
                continue
            for line in ep.read_text().splitlines():
                try:
                    url = json.loads(line)["row"]["url"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    url = None
                if url not in succeeded:
                    ef.write(line + "\n")
```

Manifest key is `{config_digest}:{batch_digest}`. Same config + same rows → manifest skips (timeout resume works). Different `max_tokens`, schema, or instruction → new config digest → all keys fresh, retry runs. Different rows → different batch digest. Per-batch fragments live in `$RD/batches/` (truncating write per key); `matches.jsonl` and `extract_errors.jsonl` are rebuilt from them at the end of each call. SIGKILL anywhere — mid-batch or mid-rebuild — leaves no duplicates: a re-run rewrites the per-batch file and rebuilds the flat outputs from the manifest's completed keys.

`extract_errors.jsonl` only carries rows that have **not** succeeded in any later batch — resolved-on-retry rows are filtered out of the flat error view at rebuild time. Per-batch fragments under `$RD/batches/errors.{key}.jsonl` retain the full history for forensics.

Rules (the SDK contracts above are already non-negotiable; these are the choices the recipe makes on top):
- **Default `BATCH=10, CONCURRENCY=3`; fan out with `asyncio.gather` + `Semaphore`** — empirically reliable, no per-call rate-limit hits, finishes ~120 rows under the 300s `bash()` ceiling. Larger batches and higher concurrency lose more on timeout and trigger upstream rate limits.
- **Schema only contains declared fields** — include `url` in the schema OR carry it forward via row-merge (`{**result, "url": row.get("url")}` in the example), not both.
- **Phrase as exclusions** — "Drop if not X" produces fewer false positives than "Include only X".
- **No regex/keyword pre- or post-filtering** — filter on `result.matches == true`. Pre-filtering to dodge `bash()` timeouts silently drops fuzzy matches (translated company names, location synonyms, truncated snippets); the resumable recipe handles latency.
- **Pass `max_tokens=16384` initially** (measured floor for filter schemas) — raise to 32768 / 65536 only when `extract_errors.jsonl` shows persistent `error.code == "max_tokens"` (or `response_decode`, same root cause). See *Handling errors* below.
- Optional kwargs: `model=` (default `gemini_3_flash`).

**Handling errors.** Group `$RD/extract_errors.jsonl` by `error.code` and decide:

- `max_tokens` (and `response_decode`, same root cause) — re-feed those rows into `filter_rows(...)` with `max_tokens=32768`, then `65536` if still failing. Persistent failure at 65536 means the schema is too rich for that profile; trim it or fall back to `client.content.fetch` + a leaner extract.
- Schema validation errors — fix the schema/instruction; the rows themselves are fine.
- Transient (timeouts, 5xx) — re-run as-is; the manifest skips completed batches.
- Anything else — sample one row, read `error.message`, decide.

Don't write an automated retry loop. Schema and persistent-budget failures don't recover from re-runs and just burn budget.

### client.content.fetch (web pages)

Returns page records: `{url, title, content, hostname, is_paywall, is_cached, error}`. Accepts a list of URLs.

```python
async with AsyncPplxClient() as client:
    res = await client.content.fetch(["https://example.com/team"])
    for p in res:
        d = p.to_dict()
        if d.get("error"):
            continue
        # d["title"], d["content"], d["hostname"], ...
```

### client.content.fetch_people (structured profile fields)

Returns one structured record per profile URL: `{url, full_name, people_headline, location, country, current_companies, previous_companies, education_ongoing, education_finished, skills, error}`. Accepts 1–50 URLs per call.

Use this **before the filter step** to enrich each candidate with fielded data the search summary doesn't expose. Summaries reliably cover name, current title/company, and location; fetch_people adds company history (current + previous), education (ongoing + finished), and skills as ready-to-read string lists. URLs the crawler can't parse as profiles return `error: "not found"` for that entry; other entries succeed independently.

Compared to `client.content.fetch` + `AsyncLlmApiClient.extract` with a custom schema: no LLM call, no token budget, fixed field set. Use the LLM-extract path only when you need fields outside the fixed set (publications, bio, specific tenure, exact dates).

```python
async with AsyncPplxClient() as client:
    res = await client.content.fetch_people([h["url"] for h in deduped[:50]])
    for r in res:
        d = r.to_dict()
        if d.get("error"):
            continue
        # d["full_name"], d["current_companies"], d["education_finished"], d["skills"], ...
```

Order is preserved; one entry per requested URL. The 50-URL ceiling is per call — loop in chunks for larger pools.

### client.content.snippets (focused extraction)

Use when summaries don't disambiguate (e.g. used a tool vs managed a team that used it), or to resolve truncated names ("First L" → full name).

```python
async with AsyncPplxClient() as client:
    res = await client.content.snippets(query="specific expertise query", urls=urls[:20])
```

The API accepts ~20 URLs per call.

### client.search.web

```python
async with AsyncPplxClient() as client:
    res = await client.search.web("Acme product team", domains=["acme.com"])
    hits = [h.to_dict() for h in res]
```

### When summaries are incomplete

`client.search.people` summaries reliably contain name, title, company, location, and the top 1–2 Experience entries. They often omit older jobs, education, publications, and bio.

- **Older jobs, education, or skills** — call `client.content.fetch_people` on the candidate URLs. Cheap (no LLM), structured (fielded), and meant for this. Feed the enriched rows to the filter step so the schema can phrase exclusions against the new fields.
- **Publications, bio, or anything outside fetch_people's fixed field set** — do a second pass on `matches.jsonl` with `client.content.fetch` (or `browser_task` if gated), then re-run `AsyncLlmApiClient.extract` against a richer schema.

Do not ask the filter-stage schema for fields the summary doesn't reliably contain and that fetch_people hasn't enriched — the model will emit `"unknown"` and it will ship.

## Recipes

**Named person lookup** — single query, no pipeline:

```python
async with AsyncPplxClient() as client:
    res = await client.search.people("Jane Doe Acme Corp", limit=10)
    print([h.to_dict() for h in res])
```

**Broad search** — full pipeline: search → dedup → enrich → filter, with optional dossier enrichment for fields outside fetch_people's fixed set.

The agent writes Python scripts and runs them via `bash()` with `api_credentials=["pplx-sdk"]`. Set `RD=/abs/path/to/ps_topic` at the top of every `bash()` call (cwd does not persist) and pass it to scripts as an argument or env var. Use a **unique `RD` per concurrent task** (subagent fan-out) so intermediate files don't collide. Workspace layout under `$RD`:

- **Scripts** go in `$RD/scripts/` with ordered, stable names — `01_search.py`, `02_enrich.py`, `03_filter.py`, `04_dossier.py`. `ls $RD/scripts/` then shows exactly what ran, in order. Never write bare `.py` files at workspace root.
- **Iterate via `apply_patch` diffs, not full rewrites** — when a script needs a tweak, patch the file. A small patch surfaces exactly what changed in the transcript; a full rewrite forces the reader to diff it in their head.
- **Step outputs** at `$RD/` root: `deduped.jsonl`, `enriched.jsonl`, `matches.jsonl`, `extract_errors.jsonl`, `filter_manifest.txt`, `dossiers.jsonl`. Filter's per-batch fragments live in `$RD/batches/`.
- **End every script with a one-line summary print** — e.g. `print(f"filter: {n_in} → {n_match} matches, {n_err} errors")` — so the `bash()` transcript and the user's scrollback both show the step's outcome at a glance.

1. **Search + dedup** — one script that runs 3+ parallel `client.search.people` queries (vary axes: role/acronym, company/expansion, industry, scope), dedups by URL keeping the longest summary, and writes `$RD/deduped.jsonl`. Scale query count to breadth: 3–5 for moderate searches, up to 10 for broad sweeps.
2. **Enrich with fetch_people** — a script that loads `$RD/deduped.jsonl`, calls `client.content.fetch_people` in chunks of 50 over all deduped URLs, and writes `$RD/enriched.jsonl`. Each row carries the original search fields **plus** `full_name`, `current_companies`, `previous_companies`, `education_ongoing`, `education_finished`, `skills` when the fetch succeeded; rows where fetch returned `error: "not found"` keep just the search fields. No LLM cost. This is what unlocks phrasing the filter step against fielded data (company history, education) instead of just the free-text summary.
3. **Filter** — a script that loads `$RD/enriched.jsonl` and calls the resumable `filter_rows(...)` recipe (criteria phrased as exclusions). Anchor the instruction on `summary` **and** the enrichment fields where they sharpen the call (`current_companies`, `education_finished`, etc.). Writes `$RD/matches.jsonl`, `$RD/extract_errors.jsonl` (full row + normalized `{code, message}` per failure), and `$RD/filter_manifest.txt`. Re-running the same script after a `bash()` timeout is safe — completed batch keys in the manifest are skipped. If `extract_errors.jsonl` is non-empty, follow *Handling errors* before continuing.
4. **Dossier enrichment (conditional)** — required when the deliverable needs publications, bio, exact tenure dates, or any field outside fetch_people's fixed set. A script that loads `$RD/matches.jsonl`, calls `client.content.fetch` on the URLs (cap ~20 per call; loop in chunks for more), then `AsyncLlmApiClient.extract` against a richer schema. Writes `$RD/dossiers.jsonl`. If a fetch returns a login wall or empty `content`, fall back to `client.search.people("<name> <company> <field>")` or `browser_task`. Do not fill dossier fields from the search summary — the model will emit `"unknown"` and it will ship.

Build the final deliverable from `dossiers.jsonl` when step 4 ran, otherwise from `matches.jsonl`.

The filter step is not optional — `client.search.people` returns many loosely-matching profiles. Without filtering, expect significant noise.

**Combined search** — use web search alongside people search for broader coverage:

1. `client.search.web("{company} {role} team", domains=["{company-domain}"])` — find team pages, directories, press releases.
2. `client.content.fetch(urls)` — read pages; extract names from `content`.
3. `client.search.people("{name} {company}", limit=10)` — enrich named candidates.

## Gotchas

These are operational footguns the SDK contract and recipe rules don't cover — things that have shipped wrong in past audits.

- **Reuse one client per script** — fan out parallel calls via `asyncio.gather` on the *same* `AsyncPplxClient`. Constructing one per coroutine leaks connections.
- **Always hyperlink the profile URL on the person's name in the final answer** — never deliver names as bare text, in a separate "LinkedIn" column, or as a trailing URL. The name *is* the link: `- [Jane Doe](https://www.linkedin.com/in/janedoe) — Senior PM, Acme (London)`. Applies to prose, tables (link the name cell, drop any standalone URL column), and md deliverables. For csv, keep a `linkedin_url` column since markdown doesn't render.
- **Never fabricate email addresses from patterns** — `firstname.lastname@company.com` guesses are unverified and have reached deliverables. Either resolve via `client.content.snippets` on the profile URL, or deliver the LinkedIn URL only and label every row `email_verified: false`.
- **Index coverage gaps** — very senior executives, public figures, people without LinkedIn profiles, and recent job changes may be absent. Fall back to `client.search.web`.
- **Names often truncated** — results frequently show "First L" instead of full names. Use `client.content.snippets` on the profile URL to resolve.
- **Don't treat `education_finished` / `previous_companies` as the canonical lists** — `fetch_people` splits schools and jobs by whether the LinkedIn entry has a `date_to`, not by whether the person actually graduated or left. A graduate with blank dates lands in `education_ongoing`; reading only `education_finished` silently drops them. Read both halves unless the task specifically turns on completion or current-vs-former status.
- **High noise at limit=100** — requesting 100 results returns 100 keyword-matched profiles, not 100 relevant ones. The extract step handles precision.