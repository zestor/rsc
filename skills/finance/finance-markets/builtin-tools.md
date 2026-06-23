# Built-in Finance Tools

Perplexity's built-in `finance_*` tools. Invoke them via `call_external_tool` with `source_id="finance"`.

**Do NOT retrieve stock prices, financial data, or company fundamentals from the open web — by any tool, shell command, URL fetch, or scraping path.** Financial data is highly specific, quantitative, and frequently revised — open-web retrieval returns stale, unstructured snippets that may reflect pre-revision figures. Built-in finance tools return structured, point-in-time accurate data directly from market data providers. Only fall back to open-web retrieval if these tools lack the specific data needed.

## Discovering Finance Tools

Discover available built-in finance tools: `list_external_tools` with `queries=["finance_"]`.

## Available Finance Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `finance_tickers_lookup` | Resolve ticker symbols (stocks, ETFs, indexes, commodities, crypto, international) | Always use first—standard tickers may not resolve, handles format variations (BRK.B vs BRK-B) and fuzzy names |
| `finance_quotes` | Real-time quotes for stocks, crypto, ETFs, indices | Current price, P/E, market cap, dividend yield. Returns markdown table |
| `finance_ohlcv_histories` | Historical OHLCV data for stocks, ETFs, crypto, indices as CSV | Price history, charts, technical indicators. Do NOT web search for historical prices—use this tool |
| `finance_company_financials` | Income statement, balance sheet, cash flow | Fundamental analysis, valuation, growth calculations, derived metrics |
| `finance_etf_holdings` | ETF constituent holdings | ETF constituents, what stocks are in an ETF, ETF breakdown |
| `finance_institutional_holders` | Institutional holders (hedge funds, mutual funds, banks) for a US ticker. US-lis |  |
| `finance_insider_transactions` | Insider transactions (Form 4 buys and sells by officers and directors) for a US  |  |
| `finance_earnings` | Earnings call transcripts with full verbatim content | Earnings call transcripts, management commentary, segment KPIs, non-GAAP metrics, guidance. Transcripts often contain drivers (take rates, unit economics, mix shifts, GMV, ARR by segment) not in financial statements |
| `finance_earnings_history` | Historical earnings actuals vs consensus estimates, beat/miss data, post-earnings price moves (returns CSV-formatted text) | EPS history, revenue beat/miss, earnings surprise metrics |
| `finance_earnings_schedule` | Earnings release dates | When companies report, upcoming/past earnings calendar |
| `finance_company_profile` | Basic company info: industry, sector, CEO, employees, website, description | Company overview, who's the CEO, what industry, employee count. Does NOT include market cap (use quotes) |
| `finance_company_peers` | Peer/comparable companies for a given ticker | Competitors, similar companies, peer comparisons, alternative investments |
| `finance_market_gainers` | Top gaining stocks/crypto today | Top gainers, what's up the most, biggest risers |
| `finance_market_losers` | Top losing stocks/crypto today | Top losers, biggest drops, what's down the most |
| `finance_market_most_active` | Most actively traded stocks today | Most active stocks, highest volume, most traded |
| `finance_market_sentiment` | Overall market sentiment analysis (bullish/bearish/neutral) | Is the market bullish or bearish, market mood, overall sentiment |
| `finance_ticker_sentiment` | Bulls vs bears analysis for a specific stock | Bull/bear case for a stock, controversial views, sentiment on a ticker |
| `finance_politician_list` | List all tracked politicians with stock activity | Which politicians trade stocks, list of tracked congress members |
| `finance_politician_holdings` | A specific politician's full stock portfolio | What stocks does [politician] own, politician's portfolio |
| `finance_politician_trades` | Recent congressional stock transactions | Recent politician trades, congressional stock transactions |
| `finance_politician_ticker_holders` | Which politicians hold a specific stock | Which politicians own [ticker], congressional holders of a stock |
| `finance_watchlist_fetch` | User's Perplexity Finance watchlist (stocks they're *tracking*, not actual brokerage holdings). | User asks about their watchlist or what stocks they're tracking. **Not for actual portfolio holdings** — use the `portfolio_holdings` connected tool for real brokerage positions. |
| `finance_segments` | Segment-level breakdowns and operating KPIs not in financial statements | Revenue models, revenue builds, unit economics, P*Q analysis, key drivers, segment growth, ARPU, GMV, take rate, store count, DAU/MAU |
| `finance_estimates` | Consensus analyst estimates and forward projections | Estimated EPS, revenue, EBITDA for future periods, consensus forecasts |
| `finance_adjusted_metrics` | Adjusted (non-GAAP) financial metrics | Adjusted EPS, adjusted EBITDA, free cash flow, management-reported metrics for valuation and peer comparison |
| `finance_analyst_research` | Analyst consensus price targets and rating changes | Price targets (avg/median/high/low), analyst ratings, upgrades/downgrades, bullish/bearish breakdown |
| `finance_company_ratios` | Company financial ratios as annual time-series | Valuation (P/E, EV/EBITDA, P/S), margins (gross, operating, net, FCF), returns (ROE, ROA, ROIC), financial health (D/E, current ratio), per-share metrics, dividends |

## Execution Pattern

All finance tools are called via `call_external_tool` with `source_id="finance"`. You **must** call `describe_external_tools` before `call_external_tool` — the system enforces this.

The sequence:

1. `list_external_tools` with `queries=["finance_"]` — discover finance tools.
2. `describe_external_tools` with `source_id="finance"` and `tool_names=["finance_quotes", "finance_company_financials"]` — fetch schemas (required before calling).
3. `call_external_tool` with `tool_name="<tool_name>"`, `source_id="finance"`, and the appropriate `arguments` — always use `source_id="finance"`.
4. Cite values from tool results when computing derived metrics — see the citations section below. Response text MUST include `[value](claim:N)` markers for every cited number.

## CSV Files

Tabular finance tools (financials, quotes, OHLCV, earnings history, estimates, etc.) return `csv_files` in the tool result — an array of entries with filenames and pre-signed download URLs. Download them to `finance_data/` before running analysis:

```bash
cd /home/user/workspace && mkdir -p finance_data
curl -sL "<url_from_csv_files>" -o "finance_data/<filename>"
```

```python
import pandas as pd
df = pd.read_csv("finance_data/AAPL_quarterly_financials.csv")
```

When citing values from a CSV, use the relevant `csv_files` entry as the `file` argument to `cite()`. Do not derive or hand-write citation metadata.

### Gotchas

- Treat explicit charting language as chart-first; generic finance lookups stay text/table-first. For chart-first queries, do NOT `curl` + pandas before `visualize` (~60s pre-paint cost). Pass `csv_files[i].url` to `visualize.sources` directly and compute cited prose metrics after the `visualize` call.

## Workflow: Always Resolve Tickers First

Never assume ticker symbols. Always use `finance_tickers_lookup` before other tools:

```python
# Single company
await call_external_tool(tool_name="finance_tickers_lookup", source_id="finance", arguments={
    "queries": ["Tesla"]
})
```

Then fetch data with the confirmed symbol:

```python
# Basic quote
await call_external_tool(tool_name="finance_quotes", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "fields": ["price", "change", "changesPercentage"]
})
```

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

## Precision

Always use exact values from finance tools — never round, approximate, or hedge. Do not use words like "approximately", "roughly", "around", "~", "nearly", or "about" when presenting financial data from tool results (e.g., "trading at $21.09/share" not "trading at approximately $21/share" or "trading around $21.09/share"). Finance tools return precise, real-time data; present it with the same precision.

## Citations

**Every numeric value pulled from a built-in `finance_*` tool — raw lookups (revenue, EPS, market cap, balance-sheet line items, estimates) AND derived values (margins, growth rates, ratios) — must:**

1. Pass through `cite()` from `skills/finance/finance-markets/citations.py`, AND
2. Appear in your response text as `[value](claim:N)` claim links.

A response with finance numbers but no claim markers is a failure.

This rule applies **even when you already know the answer**: every finance number you state must come from an actual `finance_*` tool call, pass through `cite()`, and appear as `[value](claim:N)` in your response. Short answers, follow-ups, and "obvious" lookups are not exempt — there is no shortcut. **Never type literal `[value](claim:N)` markers without actually running `cite()`** — fabricated markers look right but carry no provenance and will not render. If you produced markers without a `cite()` call, you have failed the citation requirement.

Citations apply only to built-in `finance_*` tools that return CSV files with citation provenance. They do **not** apply to BYOL connector tools or to web-search results — never call `cite()` with web or BYOL data.

### Setup

Run citation work via a `python3 << 'PYEOF'` heredoc — never `apply_patch` a `.py` file and run it (file-run scripts bypass the citation audit trail; split into multiple PYEOF calls if the heredoc gets long).

```python
# __cite_setup__
import sys
sys.path.insert(0, "skills/finance/finance-markets")
from citations import cite, load_citations, save_citations
load_citations()
# __cite_setup__
```

The `# __cite_setup__` markers form **exactly two pairs**: one around the imports/load block above, one around `save_citations()` at the end. Never wrap `cite()` calls, `print()` statements, or analysis code with these markers.

### Source values

Every number pulled from a finance tool result must include provenance fields (`source`, `file`, `row_key`, `col`). Pass the matching `csv_files` entry as `file`; it carries the tool-owned citation metadata. The `name` argument is shown in the UI; use human-readable labels like `"AAPL FY2024 Revenue"`, not snake_case.

Bind `csv_file` from the tool response's `csv_files` array before citing — paste the entry verbatim and select by filename:

```python
csv_files = [
    # paste the tool's csv_files entries here, one dict per file
    {"filename": "AAPL_quarterly_financials.csv", "url": "..."},
]
csv_file = next(f for f in csv_files if f["filename"] == "AAPL_quarterly_financials.csv")

revenue = cite(383_285_000_000, "AAPL FY2024 Revenue", source="finance_company_financials", file=csv_file, row_key="2024-Q4", col="income_statement_total_revenues")
net_income = cite(96_995_000_000, "AAPL FY2024 Net Income", source="finance_company_financials", file=csv_file, row_key="2024-Q4", col="income_statement_consolidated_net_income")
```

### Derived values

Every computed value you present (margins, growth rates, ratios, per-share metrics) **must** be cited with `formula` and `derived_from`. The names in `derived_from` must **exactly match** the parent `cite()` `name` arguments — mismatches silently break the derivation chain.

```python
margin = cite(net_income / revenue * 100, "AAPL FY2024 Net Margin", formula="net_income / revenue * 100", derived_from=["AAPL FY2024 Net Income", "AAPL FY2024 Revenue"])
growth = cite((rev_2024 - rev_2023) / rev_2023 * 100, "AAPL Revenue Growth YoY", formula="(rev_2024 - rev_2023) / rev_2023 * 100", derived_from=["AAPL FY2024 Revenue", "AAPL FY2023 Revenue"])
```

Save at the end:

```python
# __cite_setup__
save_citations()
# __cite_setup__
```

### Emitting claim links

`CitedValue` auto-formats with claim markers in f-strings — do NOT manually wrap, do NOT call `float()`/`str()` to extract first (that strips the marker):

```python
print(f"Net margin was {margin:.1f}%")          # → "Net margin was [25.3](claim:3)%"
print(f"| Revenue | ${revenue / 1e9:.1f}B |")   # → "| Revenue | $[95.4](claim:1)B |"
```

The IDs in your script's stdout are the ones you reuse in your response prose. **Never fabricate `claim:N` or `pplx://action/claim` links by hand** — only use IDs the citation flow actually generated.

### Response text — preserving citations

Your response text MUST contain `[value](claim:N)` links for every cited number. Reformat the display text for readability, but never drop the wrapper, and the link must always surround the **full display value** including units and signs:

**Correct:**

```
"Apple's revenue was **[$383.3B](claim:1)**."
"Market cap is **[$1.50T](claim:5)**."          (reformatted from [1,498,102,183,132](claim:5))
"Analysts rate it [Strong Buy](claim:12) with a target of **[$236](claim:13)**."
"representing a **[-55.8%](claim:2)** downside"
"Net margin was [50%](claim:80) in 2024."
```

**Incorrect:**

```
"Apple's revenue was $383.3B."                       — dropped the link
"Apple's revenue was $383.3B [claim:1]."             — must use markdown link, not bracket suffix
"Apple's revenue was $[383.3](claim:1)B."            — unit must be inside brackets → [$383.3B](claim:1)
"representing a [**-55.8%**](claim:2) downside"      — markdown inside link text breaks rendering
"Net margin was [50%](claim:80) in 2024 [claim:80]." — claim: doesn't take bracket-only syntax
"Market cap is **$1.50T** (claim:5)."                — must be markdown link, not bare text
```

Claim markers render as clean clickable links in the UI — never skip them "for readability," even in large tables.

### Rules summary

- One-line `cite()` calls only — no helpers, aliases, or shorthand (no `c = cite`)
- Cite values you **present** to the user — skip purely intermediate variables
- `source` must match the tool name (`finance_company_financials`, `finance_quotes`, `finance_earnings`, etc.)
- `CitedValue` extends `float` and `CitedStr` extends `str` — arithmetic and string ops preserve the claim marker through `+`, `-`, `*`, `/`, `abs()`, `round()`
- Always use f-strings with `CitedValue` (`f"{revenue:.1f}"`); plain `str()` may not trigger claim formatting
- **Never narrate citation plumbing** — do not mention the citations module, `cite()`, `save_citations`, `load_citations`, PYEOF, "I'll cite this," "I need to wrap as claim," or any other mechanic-level description in your response prose. Talk about _what the numbers mean_, never _how they're cited_.

## Data Source Routing

### Decision Tree

Follow this order for EVERY public company question. Stop at the first source that answers it:

1. **`finance_company_financials`** — Standardized income statement, balance sheet, cash flow. Use for: revenue, net income, margins, EPS, debt, cash, inventory, capex, FCF, SBC, dividends, shares outstanding, tax rates, and any ratio derivable from these (ROE, D/E, inventory turnover, payout ratio, FCF margin, CAGR, etc.)
   - **International fallback**: For tickers not covered by the primary data provider (mostly non-US exchanges), the tool automatically falls back to an alternate source. When this happens, CSV column names may use camelCase (e.g. `revenue`, `netIncome`, `totalDebt`) instead of the standard snake_case names. Read the actual CSV headers — do not assume column names match the enum values from `describe_external_tools`.

2. **`finance_earnings`** — Earnings call transcripts contain FAR more than just EPS. Use for:
   - **Forward guidance**: revenue ranges, margin targets, capex plans, growth outlook
   - **Non-GAAP metrics**: adjusted EBITDA, non-GAAP gross margin, organic growth
   - **Company-specific KPIs**: ARPU, take rate, GBV, same-store sales, nights booked, loan originations, payment volume, retention rates, subscriber counts, ASMs/RPMs, load factor
   - **Beat/miss analysis**: comparing guidance from quarter N to actuals in quarter N+1
   - **Segment breakdowns**: revenue by geography, product line, or business unit
   - **Strategic commentary**: M&A rationale, restructuring progress, competitive dynamics
   - **Adjusted EBITDA reconciliations**: line-item adjustments from net income
   - **Management Q&A**: analyst questions often surface specific data points

3. **Web search** — Only after finance tools are insufficient. Required for:
   - 10-K/10-Q footnotes (debt maturity schedules, lease obligations, acquisition details)
   - Proxy statements (director compensation, board nominations, executive pay)
   - Prospectus/8-K filings (offering terms, convertible note details, M&A consideration)
   - Risk factor narratives
   - Employee headcount/geographic data
   - Channel/vendor concentration disclosures

### Rules

- Do NOT default to open-web retrieval (search tools, shell commands, URL fetches, scraping) for public company analysis
- ALWAYS try `finance_earnings` before any open-web retrieval — transcripts answer ~50% of questions that seem like they need filings
- For questions about guidance vs. actuals, pull transcripts from BOTH the guidance quarter and the results quarter
- For hybrid questions (e.g., take rate = revenue / GBV), combine `finance_company_financials` for standardized data with `finance_earnings` for company-specific KPIs

## Per-tool reference

### Reference Date → Parameter Mapping

| Tool                          | Parameter(s) from Reference Date                                                                                            |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `finance_quotes`             | None — only use when reference date is today. Use `finance_ohlcv_histories` for past dates                                 |
| `finance_ohlcv_histories`    | `end_date_yyyy_mm_dd` = reference date                                                                                      |
| `finance_company_financials` | `as_of_fiscal_year` (always required); `as_of_fiscal_quarter` (required for `period="quarter"`, omit for `period="annual"`) |
| `finance_earnings`           | `as_of_fiscal_year`, `as_of_fiscal_quarter` (always required)                                                               |
| `finance_earnings_schedule`  | `as_of_fiscal_year`, `as_of_fiscal_quarter` (always required, unless using calendar date mode)                              |

### Ticker Lookup

Always resolve company names to tickers before fetching data using `finance_tickers_lookup`. Resolves company names, user-provided tickers, stocks, ETFs, indexes, commodities, and crypto. Handles format variations (BRK.B vs BRK-B) and partial/fuzzy names. Full support for international exchanges (.F, .L, .KS, etc.). Standard market tickers may not resolve correctly—always use this tool first.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `queries` | `list[str]` | Yes | - | Array of search queries for any financial instrument. Pass through user's phrasing when possible. Example: for query 'what is the price of NVDA, Re... |

#### Examples

```python
# Single company
await call_external_tool(tool_name="finance_tickers_lookup", source_id="finance", arguments={
    "queries": ["Tesla"]
})
```

```python
# Multiple companies
await call_external_tool(tool_name="finance_tickers_lookup", source_id="finance", arguments={
    "queries": ["Apple", "Microsoft", "Meta"]
})
```

**Handling ambiguity:** When lookup returns multiple results, present options to user or use context to disambiguate (e.g., "Meta the social media company" → META).

### Real-Time Quotes

Get current real-time quotes for stocks, cryptocurrencies, ETFs, or indices. Returns a markdown table with one row per symbol containing only the requested fields.

**Only use `finance_quotes` when the reference date is today.** For past reference dates, use `finance_ohlcv_histories` to get the closing price as of that date.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker_symbols` | `list[str]` | Yes | - | Array of ticker symbols from a prior tool call (prefer finance_tickers_lookup for ticker resolution). Examples: ["AAPL"], ["GOOGL", "META", "SNAP"]... |
| `fields` | `list[str]` | Yes | - | Required list of quote fields to include. Only request fields needed for the analysis. |

**Valid values:**

**`fields`** (QuoteField): `price`, `currency`, `change`, `changesPercentage`, `marketCap`, `pe`, `eps`, `volume`, `avgVolume`, `dayLow`, `dayHigh`, `yearLow`, `yearHigh`, `previousClose`, `open`, `dividendYieldTTM`, `afterHoursPrice`, `afterHoursChange`, `afterHoursPercentChange`

#### Examples

**Basic quote:**
```python
# Basic quote
await call_external_tool(tool_name="finance_quotes", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "fields": ["price", "change", "changesPercentage"]
})
```

**Valuation snapshot:**
```python
# Valuation snapshot
await call_external_tool(tool_name="finance_quotes", source_id="finance", arguments={
    "ticker_symbols": ["AAPL", "MSFT", "GOOGL"],
    "fields": ["price", "marketCap", "pe", "eps", "dividendYieldTTM"]
})
```

**Trading activity:**
```python
# Trading activity
await call_external_tool(tool_name="finance_quotes", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "fields": ["price", "volume", "avgVolume", "dayLow", "dayHigh"]
})
```

### Historical Data (OHLCV)

Get historical price data for stocks, ETFs, crypto, or indices. Returns OHLCV (open, high, low, close, volume) as CSV for any date range. Use this for price history, candlestick charts, and as input for technical indicator calculations. Do NOT search for historical prices—this tool provides them directly.

**Always use the reference date as `end_date_yyyy_mm_dd`.** For past reference dates, this tool replaces `finance_quotes` for price lookups.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker_symbols` | `list[str]` | Yes | - | Array of ticker symbols from a prior tool call (prefer finance_tickers_lookup for ticker resolution). Examples: ["MSFT"], ["AAPL", "GOOGL", "MSFT"]... |
| `query` | `str` | Yes | - | Human-readable query describing what price history to fetch (e.g. "Apple stock price history" or "Compare AAPL and MSFT prices"). |
| `start_date_yyyy_mm_dd` | `str` | Yes | - | Start date in YYYY-MM-DD format (e.g. "2024-01-01"). |
| `end_date_yyyy_mm_dd` | `str` | Yes | - | End date in YYYY-MM-DD format (e.g. "2024-12-31"). |
| `time_interval` | `str` | No | None | Optional—omit this field entirely to auto-select optimal interval based on date range. Only specify if user explicitly requests a particular granul... |
| `fields` | `list[str]` | Yes | - | Required list of OHLCV price fields to include in the CSV. Only request fields needed for the analysis. |
| `extended_hours` | `bool` | No | False | Set to true to include pre-market and after-hours trading data. Only enable if the user specifically asks for extended hours or after-hours data. |

**Valid values:**

**`time_interval`** (time_interval): `1min`, `5min`, `15min`, `30min`, `1hour`, `4hour`, `1day`, `1week`, `1month`

**`fields`** (PriceField): `open`, `high`, `low`, `close`, `volume`

**`time_interval` values must match the enum exactly.** Common mistakes:

- `"weekly"` → use `"1week"`
- `"monthly"` → use `"1month"`
- `"daily"` → use `"1day"`
- `"hourly"` → use `"1hour"`

#### Date Formats

Use ISO format: `YYYY-MM-DD`

#### Examples

**Specific date range:**
```python
# Specific date range
await call_external_tool(tool_name="finance_ohlcv_histories", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "start_date_yyyy_mm_dd": "2024-01-01",
    "end_date_yyyy_mm_dd": "2024-06-30"
})
```

**Multiple tickers comparison:**
```python
# Multiple tickers comparison
await call_external_tool(tool_name="finance_ohlcv_histories", source_id="finance", arguments={
    "ticker_symbols": ["AAPL", "MSFT", "GOOGL"],
    "query": "Compare AAPL, MSFT, GOOGL prices",
    "start_date_yyyy_mm_dd": "2024-01-01",
    "end_date_yyyy_mm_dd": "2024-12-31",
    "fields": ["close"]
})
```

**YTD performance:**
```python
# YTD performance
await call_external_tool(tool_name="finance_ohlcv_histories", source_id="finance", arguments={
    "ticker_symbols": ["SPY", "AAPL"],
    "query": "SPY and AAPL YTD performance",
    "start_date_yyyy_mm_dd": "2024-01-01",
    "end_date_yyyy_mm_dd": "2024-12-31",
    "fields": ["close"]
})
```

```
# Calculate: (current_close - first_close) / first_close * 100
```

**Volatility analysis:**

```python
# Fetch daily data, then calculate:
# - Daily returns: (close[i] - close[i-1]) / close[i-1]
# - Annualized volatility: std(daily_returns) * sqrt(252)
```

### ETF Holdings

Get ETF constituent holdings using `finance_etf_holdings`.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker_symbols` | `list[str]` | Yes | - | Array of ticker symbols from a prior tool call (prefer finance_tickers_lookup for ticker resolution). Examples: ["QQQ"], ["SPY", "IWM", "DIA"], ["A... |
| `ticker_names` | `list[str]` | Yes | - | Array of ETF names corresponding to ticker_symbols (e.g., ['KraneShares CSI China Internet ETF']). |
| `query` | `str` | Yes | - | The original user query requesting ETF holdings information. |

#### Examples

```python
# ETF constituents
await call_external_tool(tool_name="finance_etf_holdings", source_id="finance", arguments={
    "ticker_symbols": ["SPY", "QQQ"],
    "ticker_names": ["SPDR S&P 500 ETF", "Invesco QQQ Trust"],
    "query": "What are the top holdings in SPY and QQQ?"
})
```

### Financial Statements

Fetch financial statements (income statement, balance sheet, cash flow) using `finance_company_financials`. Specify metrics by statement type—only statements with requested metrics are fetched.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker_symbols` | `list[str]` | Yes | - | Array of ticker symbols from a prior tool call (prefer finance_tickers_lookup for ticker resolution). Examples: ["MSFT"], ["JNJ", "PFE", "ABT"], ["... |
| `period` | `str` | Yes | - | Reporting period. |
| `as_of_fiscal_year` | `str` | No | None | The most recent fiscal year to include. Data goes backward from this year. Omit to use most recent available data. |
| `as_of_fiscal_quarter` | `str` | No | None | The most recent fiscal quarter to include (1-4). Data goes backward from this quarter. Only used with quarter period. |
| `limit` | `int` | No | 1 | Number of periods to fetch going backward from as_of_fiscal_year (or from most recent if omitted) |
| `income_statement_metrics` | `list[str]` | No | [] | Revenue, profitability, and earnings metrics. |
| `balance_sheet_metrics` | `list[str]` | No | [] | Assets, liabilities, and equity metrics. |
| `cash_flow_metrics` | `list[str]` | No | [] | Operating, investing, and financing cash flows. |

**Valid values:**

**`period`** (StatementPeriod): `annual`, `quarter`, `ttm`

**`income_statement_metrics`** (IncomeStatementFieldsV3): `income_statement_total_revenues`, `income_statement_cost_of_sales`, `income_statement_gross_profit`, `income_statement_selling_general_and_administrative_expenses`, `income_statement_general_and_administrative_expenses`, `income_statement_selling_and_marketing_expenses`, `income_statement_research_and_development_expenses`, `income_statement_operating_profit`, `income_statement_interest_income`, `income_statement_interest_expense`, `income_statement_income_before_provision_for_income_taxes`, `income_statement_provision_for_income_taxes`, `income_statement_consolidated_net_income`, `income_statement_net_income_attributable_to_minority_interests_and_other`, `income_statement_net_income_attributable_to_common_shareholders`, `income_statement_basic_eps`, `income_statement_diluted_eps`, `income_statement_basic_weighted_average_shares_outstanding`, `income_statement_diluted_weighted_average_shares_outstanding`, `income_statement_non_operating_income`, `income_statement_non_operating_income_or_expense`, `income_statement_benefits_and_claims`, `income_statement_compensation_expenses`, `income_statement_depreciation_and_amortization_expenses`, `income_statement_investment_expense`, `income_statement_investment_income`, `income_statement_net_gains_losses_on_investments`, `income_statement_net_income_attributable_to_discontinued_operations`, `income_statement_net_income_attributable_to_preferred_dividends`, `income_statement_net_interest_income`, `income_statement_net_premiums_earned`, `income_statement_non_interest_income`, `income_statement_other_non_interest_expenses`, `income_statement_other_operating_expenses`, `income_statement_other_revenues`, `income_statement_policy_amortization_costs`, `income_statement_provision_for_credit_losses`, `income_statement_total_non_interest_expense`, `income_statement_total_other_revenues`, `income_statement_total_revenues_after_provision_for_credit_losses`, `income_statement_total_revenues_before_provision_for_credit_losses`, `income_statement_transaction_based_revenues`, `ratio_gross_profit_margin`, `ratio_operating_margin`, `ratio_ebitda_margin`, `ratio_net_profit_margin`, `ratio_effective_tax_rate`, `ratio_pre_tax_profit_margin`

**`balance_sheet_metrics`** (BalanceSheetFieldsV3): `balance_sheet_cash_and_cash_equivalents`, `balance_sheet_short_term_investments`, `balance_sheet_accounts_receivable`, `balance_sheet_total_trade_receivables`, `balance_sheet_inventories`, `balance_sheet_other_current_assets`, `balance_sheet_total_current_assets`, `balance_sheet_net_property_plant_and_equipment`, `balance_sheet_goodwill`, `balance_sheet_net_intangible_assets`, `balance_sheet_long_term_investments`, `balance_sheet_other_non_current_assets`, `balance_sheet_other_non_earning_assets`, `balance_sheet_other_assets`, `balance_sheet_total_assets`, `balance_sheet_accounts_payable`, `balance_sheet_short_term_debt`, `balance_sheet_unearned_revenue`, `balance_sheet_other_current_liabilities`, `balance_sheet_total_current_liabilities`, `balance_sheet_long_term_debt`, `balance_sheet_other_long_term_liabilities`, `balance_sheet_total_long_term_liabilities`, `balance_sheet_other_liabilities`, `balance_sheet_total_liabilities`, `balance_sheet_preferred_stock`, `balance_sheet_common_stock`, `balance_sheet_retained_earnings`, `balance_sheet_accumulated_other_comprehensive_income`, `balance_sheet_total_shareholders_equity`, `balance_sheet_total_common_shareholders_equity`, `balance_sheet_total_investments`, `balance_sheet_total_debt`, `balance_sheet_total_cash_and_cash_equivalents`, `balance_sheet_total_liabilities_and_shareholders_equity`, `balance_sheet_accrued_expenses`, `balance_sheet_additional_paid_in_capital`, `balance_sheet_current_portion_of_leases`, `balance_sheet_leases`, `balance_sheet_other_long_term_assets`, `balance_sheet_accrued_interest_and_accounts_receivable`, `balance_sheet_claims_reserves`, `balance_sheet_current_portion_of_long_term_debt`, `balance_sheet_debt_securities`, `balance_sheet_deferred_acquisition_costs`, `balance_sheet_equity_and_preferred_securities`, `balance_sheet_gross_loans`, `balance_sheet_interest_bearing_deposits`, `balance_sheet_less_allowance_for_loan_losses`, `balance_sheet_minority_interests_and_other`, `balance_sheet_net_loans`, `balance_sheet_noninterest_bearing_deposits`, `balance_sheet_other_investments`, `balance_sheet_other_receivables`, `balance_sheet_recontract_assets`, `balance_sheet_restricted_cash_and_segregated_assets`, `balance_sheet_securities_and_investments`, `balance_sheet_securities_borrowed`, `balance_sheet_securities_loaned`, `balance_sheet_short_term_borrowings`, `balance_sheet_short_term_interbank_borrowing_and_repurchase_agreements`, `balance_sheet_short_term_interbank_lending_and_reverse_repurchase_agreements`, `balance_sheet_total_deposits`, `balance_sheet_trading_assets`, `balance_sheet_trading_liabilities`, `balance_sheet_treasury_stock`, `balance_sheet_unearned_premiums`

**`cash_flow_metrics`** (CashFlowFieldsV3): `cash_flow_statement_net_income`, `cash_flow_statement_depreciation_and_amortization`, `cash_flow_statement_share_based_compensation_expense`, `cash_flow_statement_other_adjustments`, `cash_flow_statement_changes_in_trade_receivables`, `cash_flow_statement_changes_in_accounts_payable`, `cash_flow_statement_changes_in_accrued_expenses`, `cash_flow_statement_changes_in_unearned_revenue`, `cash_flow_statement_changes_in_other_operating_activities`, `cash_flow_statement_cash_from_operating_activities`, `cash_flow_statement_purchases_of_property_plant_and_equipment`, `cash_flow_statement_proceeds_from_sale_of_property_plant_and_equipment`, `cash_flow_statement_purchases_of_investments`, `cash_flow_statement_proceeds_from_sale_of_investments`, `cash_flow_statement_payments_for_business_acquisitions`, `cash_flow_statement_other_investing_activities`, `cash_flow_statement_cash_from_investing_activities`, `cash_flow_statement_issuance_of_long_term_debt`, `cash_flow_statement_repayments_of_long_term_debt`, `cash_flow_statement_net_issuance_or_repayments_of_long_term_debt`, `cash_flow_statement_issuance_of_common_shares`, `cash_flow_statement_repurchases_of_common_shares`, `cash_flow_statement_net_issuance_or_repurchases_of_common_shares`, `cash_flow_statement_issuance_of_preferred_shares`, `cash_flow_statement_net_issuance_or_repurchases_of_preferred_shares`, `cash_flow_statement_common_share_dividends_paid`, `cash_flow_statement_other_financing_activities`, `cash_flow_statement_cash_from_financing_activities`, `cash_flow_statement_effect_of_exchange_rate_changes_on_cash_and_cash_equivalents`, `cash_flow_statement_increase_or_decrease_in_cash_cash_equivalents_and_restricted_cash`, `cash_flow_statement_cash_cash_equivalents_and_restricted_cash_at_beginning_of_period`, `cash_flow_statement_changes_in_accrued_interest_and_accounts_receivable`, `cash_flow_statement_changes_in_claims_reserves`, `cash_flow_statement_changes_in_deferred_acquisition_costs`, `cash_flow_statement_changes_in_income_taxes_payable`, `cash_flow_statement_changes_in_inventories`, `cash_flow_statement_changes_in_receivables`, `cash_flow_statement_changes_in_recontract_assets`, `cash_flow_statement_changes_in_restricted_cash_and_segregated_assets`, `cash_flow_statement_changes_in_securities_borrowed`, `cash_flow_statement_changes_in_trading_assets`, `cash_flow_statement_changes_in_trading_liabilities`, `cash_flow_statement_changes_in_unearned_premiums`, `cash_flow_statement_issuance_of_short_term_debt`, `cash_flow_statement_net_change_in_deposits`, `cash_flow_statement_net_change_in_loans_held_for_investment`, `cash_flow_statement_net_change_in_loans_held_for_sale`, `cash_flow_statement_net_change_in_securities_and_investments`, `cash_flow_statement_net_change_in_short_term_interbank_borrowing_and_repurchase_agreements`, `cash_flow_statement_net_change_in_short_term_interbank_lending_and_reverse_repurchase_agreements`, `cash_flow_statement_net_issuance_or_repayments_of_short_term_debt`, `cash_flow_statement_preferred_share_dividends_paid`, `cash_flow_statement_proceeds_from_business_divestments`, `cash_flow_statement_purchases_of_intangible_assets`, `cash_flow_statement_repayments_of_short_term_debt`, `cash_flow_statement_repurchases_of_preferred_shares`

**Metric names must match the enum exactly.** Common mistakes:

- `weightedAverageShsOut` → use `weightedAverageSharesOutstanding`
- `weightedAverageShsOutDil` → use `weightedAverageSharesOutstandingDiluted`
- `accountPayables` → use `accountsPayables`
- `dividendsPaid` → use `netDividendsPaid`, `commonDividendsPaid`, or `preferredDividendsPaid`

#### Field Formats

- Ratio fields (`ebitdaRatio`, etc.) are decimals: 0.65 = 65%
- `eps`/`epsDiluted` are currency per share: 0.39 = $0.39
- `weightedAverageSharesOutstanding` fields are raw counts
- All other numeric fields are raw currency in `reportedCurrency` (not abbreviated)

#### Examples

**Current Data (always pass as_of from reference date):**
```python
# Tesla's latest revenue (use quarter for current state)
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["TSLA"],
    "period": "quarter",
    "as_of_fiscal_year": 2025,
    "as_of_fiscal_quarter": 1,
    "limit": 1,
    "income_statement_metrics": ["income_statement_total_revenues"]
})
```

**Apple's last 5 years FCF:**
```python
# Apple's last 5 years FCF (no direct FCF field — fetch OCF and capex, compute FCF = OCF - capex)
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period": "annual",
    "as_of_fiscal_year": 2025,
    "limit": 5,
    "cash_flow_metrics": ["cash_flow_statement_cash_from_operating_activities", "cash_flow_statement_purchases_of_property_plant_and_equipment"]
})
```

**Historical Data (as_of from explicit past reference date):**
```python
# Rivian revenue from 2023 Q3 back 4 quarters
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["RIVN"],
    "period": "quarter",
    "as_of_fiscal_year": 2023,
    "as_of_fiscal_quarter": 3,
    "limit": 4,
    "income_statement_metrics": ["income_statement_total_revenues"]
})
```

**Cross-Statement:**
```python
# Apple net income, cash position, and operating cash flow
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period": "annual",
    "as_of_fiscal_year": 2025,
    "limit": 1,
    "income_statement_metrics": ["income_statement_consolidated_net_income"],
    "balance_sheet_metrics": ["balance_sheet_cash_and_cash_equivalents"],
    "cash_flow_metrics": ["cash_flow_statement_cash_from_operating_activities"]
})
```

**TTM (Trailing Twelve Months):**
```python
# NVDA TTM gross profit
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["NVDA"],
    "period": "ttm",
    "income_statement_metrics": ["income_statement_gross_profit"]
})
```

**Growth Calculations (fetch multiple periods to compare):**
```python
# Apple YoY revenue growth (fetch 2 periods, compute delta)
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period": "annual",
    "as_of_fiscal_year": 2025,
    "limit": 2,
    "income_statement_metrics": ["income_statement_total_revenues"]
})
```

```
# Calculate: (current - previous) / previous
```

**Derived Metrics (fetch component fields for calculation):**
```python
# Apple debt-to-equity ratio (fetch components, compute ratio)
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period": "quarter",
    "as_of_fiscal_year": 2025,
    "as_of_fiscal_quarter": 1,
    "limit": 1,
    "balance_sheet_metrics": ["balance_sheet_total_debt", "balance_sheet_total_shareholders_equity"]
})
```

```
# Calculate: balance_sheet_total_debt / balance_sheet_total_shareholders_equity
```

### Earnings Transcripts

Get earnings call transcripts using `finance_earnings`.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker_symbol` | `str` | Yes | - | Ticker symbol from a prior tool call (prefer finance_tickers_lookup for ticker resolution). Examples: 'TSLA', 'GOOGL', 'JPM'. |
| `query` | `str` | Yes | - | Human-readable description of the earnings data request |
| `as_of_fiscal_quarter` | `str` | No | None | The most recent fiscal quarter to include (1-4). Data goes backward from this quarter. |
| `as_of_fiscal_year` | `str` | No | None | The most recent fiscal year to include. Data goes backward from this year. Omit to use most recent available data. |
| `limit` | `int` | No | 1 | Number of earnings periods to fetch going backward from as_of period (or from most recent if omitted) |
| `data_types` | `list[str]` | No | ['earnings_history'] | Types of earnings data to retrieve. |

#### Examples

**Current Data (always pass as_of from reference date):**
```python
# Tesla's latest earnings call
await call_external_tool(tool_name="finance_earnings", source_id="finance", arguments={
    "ticker_symbol": "TSLA",
    "as_of_fiscal_year": 2025,
    "as_of_fiscal_quarter": 1,
    "limit": 1,
    "data_types": ["transcript_full"]
})
```

**Apple's last 3 earnings calls:**
```python
# Apple's last 3 earnings calls
await call_external_tool(tool_name="finance_earnings", source_id="finance", arguments={
    "ticker_symbol": "AAPL",
    "as_of_fiscal_year": 2025,
    "as_of_fiscal_quarter": 1,
    "limit": 3,
    "data_types": ["transcript_full"]
})
```

**Historical Data (as_of from explicit past reference date):**
```python
# Microsoft Q4 2024 earnings call
await call_external_tool(tool_name="finance_earnings", source_id="finance", arguments={
    "ticker_symbol": "MSFT",
    "as_of_fiscal_year": 2024,
    "as_of_fiscal_quarter": 4,
    "limit": 1,
    "data_types": ["transcript_full"]
})
```

**Google earnings from 2022 back 4 quarters:**
```python
# Google earnings from 2022 back 4 quarters
await call_external_tool(tool_name="finance_earnings", source_id="finance", arguments={
    "ticker_symbol": "GOOGL",
    "as_of_fiscal_year": 2022,
    "as_of_fiscal_quarter": 4,
    "limit": 4,
    "data_types": ["transcript_full"]
})
```

### Earnings History

Get historical earnings actuals vs consensus estimates, beat/miss data, and post-earnings price moves using `finance_earnings_history` (returns CSV-formatted text).

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker_symbols` | `list[str]` | Yes | - | Array of ticker symbols from a prior tool call (prefer finance_tickers_lookup for ticker resolution). Examples: ["AAPL"], ["NFLX", "DIS", "WBD"], [... |
| `period_type` | `str` | No | 'quarterly' | Reporting period. |
| `as_of_fiscal_quarter` | `str` | No | None | The most recent fiscal quarter to include (1-4). Data goes backward from this quarter. |
| `as_of_fiscal_year` | `str` | No | None | The most recent fiscal year to include. Data goes backward from this year. Omit to use most recent available data. |
| `limit` | `int` | No | 8 | How many prior reporting periods to return, going backward from the as_of period. |

#### Examples

**Earnings Metrics:**
```python
# AAPL earnings beat/miss history
await call_external_tool(tool_name="finance_earnings_history", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period_type": "quarterly",
    "limit": 8
})
```

### Earnings Schedule

Look up earnings release dates and reporting status using `finance_earnings_schedule`. Always pass `as_of_fiscal_year`/`as_of_fiscal_quarter` derived from the reference date, except in calendar date mode (`start_date`/`end_date`).

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker_symbols` | `list[str]` | No | [] | Array of ticker symbols from a prior tool call (prefer finance_tickers_lookup for ticker resolution). Examples: ["MSFT"], ["GOOGL", "META", "SNAP"]... |
| `direction` | `str` | No | None | Historical or future earnings dates. Omit when using date range or fiscal period filters. |
| `start_date` | `str` | No | None | Start of date range (YYYY-MM-DD). Use for calendar-based queries like 'this week' or 'next month'. |
| `end_date` | `str` | No | None | End of date range (YYYY-MM-DD). Use with start_date for calendar-based queries. |
| `as_of_fiscal_year` | `str` | No | None | Fiscal year to look up. Use for period-based queries like 'Q4 2024'. |
| `as_of_fiscal_quarter` | `str` | No | None | Fiscal quarter to look up (1-4). Use with as_of_fiscal_year for specific quarter queries. |
| `limit` | `int` | No | 1 | Number of earnings events to return per ticker. Use >1 for queries like 'last 4 quarters'. |

**Mode rules:** Calendar date mode (`start_date`/`end_date`) and fiscal period mode (`as_of_fiscal_year`/`as_of_fiscal_quarter`) are mutually exclusive. Omit both for default behavior (next upcoming + most recent past).

#### Examples

**Calendar (all companies in date range):**
```python
# All earnings this week
await call_external_tool(tool_name="finance_earnings_schedule", source_id="finance", arguments={
    "ticker_symbols": [],
    "start_date": "2025-02-03",
    "end_date": "2025-02-07"
})
```

**Ticker + Date Range:**
```python
# Apple earnings in February
await call_external_tool(tool_name="finance_earnings_schedule", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "start_date": "2025-02-01",
    "end_date": "2025-02-28"
})
```

**Ticker + Fiscal Period:**
```python
# Apple Q4 2024 earnings date
await call_external_tool(tool_name="finance_earnings_schedule", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "as_of_fiscal_year": 2024,
    "as_of_fiscal_quarter": 4
})
```

**Default (next upcoming + most recent past):**
```python
# When does Apple report next?
await call_external_tool(tool_name="finance_earnings_schedule", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "as_of_fiscal_year": 2025,
    "as_of_fiscal_quarter": 1
})
```

**Use cases:**

- "When does AAPL report?" → default mode with ticker
- "Earnings this week" → calendar mode with empty ticker list
- "Did NVDA already report Q3?" → fiscal period mode
- "Last 4 quarters of MSFT earnings dates" → default mode with limit=4

For earnings transcripts, use `finance_earnings`. For EPS history and beat/miss metrics, use `finance_earnings_history`.

### Ticker Sentiment

Get bulls vs bears analysis for a specific stock ticker using `finance_ticker_sentiment`. Returns controversial issues with both bull and bear viewpoints, backed by citations from recent news and analysis.

For overall market sentiment (not ticker-specific), use `finance_market_sentiment` instead.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker_symbol` | `str` | Yes | - | Ticker symbol from a prior tool call (prefer finance_tickers_lookup for ticker resolution). Examples: 'PLTR', 'TSLA', 'SOFI'. |
| `query` | `str` | Yes | - | The original user query about the stock. |
| `action` | `str` | Yes | - | Action being performed, written in present progressive tense. Describe the analysis being performed. Example: "Analyzing bulls vs bears for NVDA" |

#### Examples

**Bulls vs bears for a stock:**
```python
# Bulls vs bears for a stock
await call_external_tool(tool_name="finance_ticker_sentiment", source_id="finance", arguments={
    "ticker_symbol": "TSLA",
    "query": "What's the bull and bear case for Tesla?",
    "action": "Analyzing bulls vs bears for Tesla"
})
```

## Quick Reference

### Get current quote

```python
# Valuation snapshot
await call_external_tool(tool_name="finance_quotes", source_id="finance", arguments={
    "ticker_symbols": ["AAPL", "MSFT", "GOOGL"],
    "fields": ["price", "marketCap", "pe", "eps", "dividendYieldTTM"]
})
```

### Get historical data

```python
# Specific date range
await call_external_tool(tool_name="finance_ohlcv_histories", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "start_date_yyyy_mm_dd": "2024-01-01",
    "end_date_yyyy_mm_dd": "2024-06-30"
})
```

### Get recent financial data (always pass as_of from reference date)

```python
# Tesla's latest revenue (use quarter for current state)
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["TSLA"],
    "period": "quarter",
    "as_of_fiscal_year": 2025,
    "as_of_fiscal_quarter": 1,
    "limit": 1,
    "income_statement_metrics": ["income_statement_total_revenues"]
})
```

### Get historical financial data

```python
# Rivian revenue from 2023 Q3 back 4 quarters
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["RIVN"],
    "period": "quarter",
    "as_of_fiscal_year": 2023,
    "as_of_fiscal_quarter": 3,
    "limit": 4,
    "income_statement_metrics": ["income_statement_total_revenues"]
})
```

### Get derived financial metrics

```python
# Apple net income, cash position, and operating cash flow
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period": "annual",
    "as_of_fiscal_year": 2025,
    "limit": 1,
    "income_statement_metrics": ["income_statement_consolidated_net_income"],
    "balance_sheet_metrics": ["balance_sheet_cash_and_cash_equivalents"],
    "cash_flow_metrics": ["cash_flow_statement_cash_from_operating_activities"]
})
```

### Get recent earnings transcript (always pass as_of from reference date)

```python
# Tesla's latest earnings call
await call_external_tool(tool_name="finance_earnings", source_id="finance", arguments={
    "ticker_symbol": "TSLA",
    "as_of_fiscal_year": 2025,
    "as_of_fiscal_quarter": 1,
    "limit": 1,
    "data_types": ["transcript_full"]
})
```

### Get historical earnings transcript

```python
# Microsoft Q4 2024 earnings call
await call_external_tool(tool_name="finance_earnings", source_id="finance", arguments={
    "ticker_symbol": "MSFT",
    "as_of_fiscal_year": 2024,
    "as_of_fiscal_quarter": 4,
    "limit": 1,
    "data_types": ["transcript_full"]
})
```

### Get earnings beat/miss history

```python
# AAPL earnings beat/miss history
await call_external_tool(tool_name="finance_earnings_history", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period_type": "quarterly",
    "limit": 8
})
```

### Get earnings schedule (always pass as_of from reference date)

```python
# When does Apple report next?
await call_external_tool(tool_name="finance_earnings_schedule", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "as_of_fiscal_year": 2025,
    "as_of_fiscal_quarter": 1
})
```

```python
# All earnings this week
await call_external_tool(tool_name="finance_earnings_schedule", source_id="finance", arguments={
    "ticker_symbols": [],
    "start_date": "2025-02-03",
    "end_date": "2025-02-07"
})
```

```python
# Apple Q4 2024 earnings date
await call_external_tool(tool_name="finance_earnings_schedule", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "as_of_fiscal_year": 2024,
    "as_of_fiscal_quarter": 4
})
```

### Get ETF holdings

```python
# ETF constituents
await call_external_tool(tool_name="finance_etf_holdings", source_id="finance", arguments={
    "ticker_symbols": ["SPY", "QQQ"],
    "ticker_names": ["SPDR S&P 500 ETF", "Invesco QQQ Trust"],
    "query": "What are the top holdings in SPY and QQQ?"
})
```

### Get institutional holders

```python
# Institutional holders
await call_external_tool(tool_name="finance_institutional_holders", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"]
})
```

### Get insider transactions

```python
# Insider transactions last 3 months
await call_external_tool(tool_name="finance_insider_transactions", source_id="finance", arguments={
    "ticker_symbols": ["NVDA"],
    "months_lookback": 3
})
```
