# Building Websites with Live Portfolio Data

**Load the `programmatic-tool-calling` skill** and use the `external-tool` CLI with `source_id="plaid"` from the website's backend for **every** portfolio data request. Start the server with `api_credentials=["external-tools"]`. Cache responses server-side (5–15 min TTL) — portfolio data updates once daily so aggressive caching is fine.

## Rules

- Every portfolio endpoint must call `external-tool` on every request (with server-side caching)
- Do NOT call a portfolio tool once to seed a local database — that makes the data stale
- Do NOT hardcode portfolio data or inline results from a one-off `call_external_tool` into the website source
- If the user doesn't have Plaid connected, show an auth prompt — do NOT fall back to fabricated demo data

## Common Gotchas

### Seed-and-forget

Wrong: calling `call_external_tool("portfolio_holdings")` once, copying the results into a `SEED_DATA` constant with hardcoded tickers, prices, and quantities, and loading it into SQLite on startup. The endpoint then reads from the database and never calls the CLI again.

```javascript
// WRONG — data is frozen at build time
const SEED_DATA = [
  { ticker: "AAPL", quantity: 50, price: 224.72, value: 11236.00 },
  { ticker: "NVDA", quantity: 25, price: 112.83, value: 2820.75 },
];
app.get("/api/holdings", (_req, res) => res.json(db.getAll()));

// RIGHT — fetched live on every request
app.get("/api/holdings", (_req, res) => {
  const data = callTool("plaid", "portfolio_holdings", {});
  res.json(data);
});
```

### Fabricated demo data as fallback

Wrong: catching an error from the Plaid tool call and returning hardcoded fake portfolio data via a `getDemoData()` function. The user sees made-up holdings that don't match their actual account.

If the tool returns `auth_required`, surface the error to the frontend so the user can connect their brokerage. Never fabricate financial data.

### Static site deploy with backend routes

Wrong: writing correct `external-tool` CLI calls in Express routes, then deploying only the `dist/public` folder as a static site. The backend never runs in production — the live API endpoints don't exist after deploy.

If the website needs live portfolio data, it must be deployed with the backend server running, not as a static site.
