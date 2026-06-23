# Building finance websites

Loaded on demand when producing dashboards, reports with embedded charts, or any web output backed by finance data.

## Cross-cutting rules

1. Use `programmatic-tool-calling` for every finance data fetch.

   **Load the `programmatic-tool-calling` skill** and invoke finance tools from the website's backend via the `external-tool` CLI. Start the server with `api_credentials=["external-tools"]`.

2. Cache server-side (15–30s TTL for market data; 5–15 min for slower-moving aggregates). Never fetch directly from the browser.
3. No static deploys — data must be fetched at request time so reference dates stay correct.
4. Never fabricate data. If a tool returns no value, render `"—"` or hide the row; never invent figures.
5. Do NOT call third-party data APIs (FMP, Yahoo Finance, etc.) directly — all finance data must flow through the `external-tool` CLI.
6. Do NOT call a finance tool once to seed a local database — that makes the data stale.

## Reference Date

Most time-sensitive finance tools (`company_financials`, `earnings`, `earnings_schedule`, `ohlcv_histories`) take a **reference date** that determines what data to fetch. ALWAYS derive `as_of` parameters from this date — never omit them.

### Step 1: Identify the Reference Date

- If the user specifies an explicit date (e.g., "as of March 2024"), use that date
- If the user's question implies a time period (e.g., "Q4 2024 results", "last year's revenue", "2023 earnings call"), infer the closest reference date that would return the relevant data
- Otherwise, use the current date/time from the `<context>` block

### Step 2: Map to Fiscal Parameters

`as_of_fiscal_year` and `as_of_fiscal_quarter` use the **company's fiscal calendar** — pass the fiscal period the user is asking about, not a calendar-mapped equivalent.

- If the user specifies a fiscal period directly, pass it as-is
- Otherwise, determine the company's fiscal calendar and map the reference date to the correct fiscal period

Do NOT assume Jan–Dec fiscal years.

### Rules

- **NEVER** omit `as_of` parameters — "latest" is ambiguous and non-reproducible
- For historical price lookups, use the reference date as the explicit end date on OHLCV-style tools

## Common gotchas

### Seed-and-forget

Wrong: calling `call_external_tool(...)` once, copying the results into a `SEED_DATA` constant, and loading it into SQLite on startup. The endpoint then reads from the database and never calls the CLI again — data is frozen at build time.

```javascript
// WRONG — data is stale the moment the server starts
const SEED_DATA = [
  { symbol: 'NVDA', price: 165.17, change: -2.35 },
  { symbol: 'TSLA', price: 272.1, change: 3.5 },
];
app.get('/api/watchlist', (_req, res) => res.json(db.getAll()));

// RIGHT — fetched live on every request
app.get('/api/watchlist', (_req, res) => {
  const data = callTool('finance', 'finance_watchlist_fetch', {});
  res.json(data);
});
```

### Static site deploy with backend routes

Wrong: writing correct `external-tool` CLI calls in Express routes, then deploying only the `dist/public` folder as a static site. The backend never runs in production — the live API endpoints don't exist after deploy.

If the website needs live finance data, it must be deployed with the backend server running, not as a static site.

### Fabricated data in frontend components

Wrong: hardcoding tickers, prices, or metrics directly in React components because "the API wasn't ready yet." Those values ship to production and the user sees made-up numbers.

## Built-in `finance_*` data handling

- Responses include `csv_files` with pre-signed download URLs. Download them to `finance_data/` on the backend and read with pandas — do not stream CSV through the client.
- For cited prose metrics, pass the matching `csv_files` entry to `cite(file=...)` per `builtin-tools.md`.

For BYOL providers (the `list_external_tools` set enumerated in `SKILL.md`), call via `call_external_tool` with `source_id="<provider>"` from the backend handler. Store responses in a server-side cache (Redis or in-memory with TTL) keyed by request parameters. Do not attempt to cite via the `citations` module; provenance for BYOL responses lives in the response payload itself. Connector-specific guidance (loaded via `load_skill` after `list_external_tools`) supersedes any general guidance here.
