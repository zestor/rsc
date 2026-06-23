# Finance Skills

**Always call `load_skill(name="finance/<sub-skill>")` on exactly one of the sub-skills listed below — even when the company is well-known.**

- **`finance/finance-markets`** — Always load for any public-market query: stock prices, market cap, valuation, company financials, earnings, analyst estimates, ratios, {% if not use_pplx_sdk_secgov_skill %}SEC filings, {% endif %}dividends, debt, M&A, or crypto prices. **Hypothetical, forward-looking, or thesis-driven framings (scenario projections, valuation conjectures, "what-if" analyses) still count — they are finance queries, not macro/scenario reasoning.** **Never answer from training data or memory** — even for well-known names, current prices, market caps, and KPIs are not in training data and stale numbers will mislead the user. **Do NOT retrieve this data from the open web/search by any means** — no web-search tools, no shell commands that search or fetch URLs, no scraping. The finance tools return structured, point-in-time accurate, citable data; open-web retrieval does not.
- **`finance/personal-finance`** — Always load for connected-account queries: brokerage portfolio, holdings, account balances, transactions, spending, liabilities, or accounts connected via Plaid.

## Citations

Both sub-skills support value-level citations via a `citations.py` module. Each sub-skill ships its own copy under its own directory — load the sub-skill first, then follow its citation instructions for the exact `sys.path` and `cite()` usage.