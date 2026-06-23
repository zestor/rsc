# Personal Finance Tools

Tools for accessing the user's connected financial account data via Plaid. These return **private user data** (holdings, balances, transactions, liabilities), not public market data.

## Bootstrap

Discover available personal-finance providers: `list_external_tools` with `queries=["plaid"]`.

If no connector skill is hinted, follow the patterns below for the built-in Plaid tools.

## Available Personal Finance Tools

All tools use `source_id="plaid"`.

| Tool                           | Purpose                                                                                | When to Use                                                                                                                                                              |
| ------------------------------ | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `portfolio_holdings`  | Detailed positions with ticker, quantity, price, value, day change, gain/loss          | User asks about their holdings, positions, or what stocks they own                                                                                                       |
| `portfolio_summary`   | Aggregate portfolio stats (total value, day change, gain/loss) and noteworthy holdings | User asks for a portfolio summary or overall performance                                                                                                                 |
| `account_balance`     | Current balances across connected bank accounts and credit cards                       | User asks about their account balance or cash available                                                                                                                  |
| `transaction_history` | Search/filter/aggregate bank and credit card transactions                              | User asks about recent transactions, spending, or payment history                                                                                                        |
| `liabilities`         | Comprehensive debt view (interest rates, APRs, loan terms, overdue flags)              | User asks about their debts, loans, or credit card balances                                                                                                              |
| `financial_profile`   | Self-reported household income bracket and risk comfort level                          | User asks about their financial profile, income bracket, or risk tolerance — also load when tailoring general financial advice or investment recommendations to the user |

## Execution Pattern

You **must** call `describe_external_tools` before `call_external_tool` — the system enforces this.

The sequence:

1. `list_external_tools` with `queries=["plaid"]` — confirm the source is connected.
2. `describe_external_tools` with `source_id="plaid"` and `tool_names=["portfolio_holdings", "portfolio_summary", "account_balance"]` — fetch schemas.
3. `call_external_tool` with `tool_name="portfolio_holdings"`, `source_id="plaid"`, and `arguments={}` — invoke.

If the user does not have Plaid connected, the tool call will return an `auth_required` error. Surface this to the user rather than falling back to fabricated data.

## CSV Files

Plaid tools that return tabular data (`portfolio_holdings`, `transaction_history`) return `csv_files` in the tool result — an array of entries with filenames and pre-signed download URLs. Download them to `finance_data/` before running analysis:

```bash
cd /home/user/workspace && mkdir -p finance_data
curl -sL "<url_from_csv_files>" -o "finance_data/<filename>"
```

```python
import pandas as pd
df = pd.read_csv("finance_data/portfolio_holdings.csv")
```

When citing values from a CSV, use the relevant `csv_files` entry as the `file` argument to `cite()`.

## Citations

**MANDATORY**: Every private financial value you present to the user MUST be wrapped as `[value](claim:N)` in your response text. A response that shows holdings, balances, transactions, or liabilities without claim markers is a failure. This is how the frontend renders personal-finance pills, applies author-view masking, and shares threads safely. Unwrapped private values cannot be masked and leak when the thread is shared.

After running your Python script, your response text MUST contain claim links like `[$45,000](claim:2)` for every private value — including values inside **markdown table cells**.

**NEVER call `cite()` with web search data or fabricated values.** The `cite()` function requires provenance fields (`source`, `file`, `row_key`, `col`) that come from personal-finance tool CSV output. ALL values passed to `cite()` MUST come from personal-finance tool results.

For values from a tool CSV, pass the relevant `csv_files` entry to `cite(file=...)`.

```python
# __cite_setup__
import sys
sys.path.insert(0, "skills/finance/personal-finance")
from citations import cite, load_citations, save_citations
load_citations()
# __cite_setup__
```

The `# __cite_setup__` markers form **two separate pairs** — one around imports/load at the top, one around `save_citations()` at the bottom. Everything between the pairs (`cite()` calls, derived metrics, `print()` statements) MUST remain outside the markers.

**Cite source values** — every number pulled from a personal-finance tool result.
The `name` argument is shown directly in the UI — use human-readable labels
like "AAPL Position Value", not snake_case identifiers.
The `source`, `file`, `row_key`, and `col` arguments identify the provenance cell.

Bind `csv_file` from the tool response's `csv_files` array — paste the entry verbatim and select by filename:

```python
csv_files = [
    # paste the tool's csv_files entries here, one dict per file
    {"filename": "portfolio_holdings.csv", "url": "..."},
]
csv_file = next(f for f in csv_files if f["filename"] == "portfolio_holdings.csv")

total_value = cite(125_000.50, "Total Portfolio Value", source="portfolio_holdings", file=csv_file, row_key="TOTAL", col="Value")
aapl_value = cite(45_000.00, "AAPL Position Value", source="portfolio_holdings", file=csv_file, row_key="AAPL", col="Value")
aapl_qty = cite(100, "AAPL Quantity", source="portfolio_holdings", file=csv_file, row_key="AAPL", col="Quantity")

# For transactions, `row_key` is the opaque Transaction ID — DO NOT use it as the
# `name`. Build a readable name from merchant + date + column instead.
txn_amount = cite(87.43, "Whole Foods 2026-03-12 Amount", source="transaction_history", file=csv_file, row_key="<transaction_id>", col="Amount")
```

### Citing Derived Values

Every computed value you present to the user MUST be cited with `formula` and `derived_from`. Both are required for the derivation chain.

**Portfolio weights:**

```python
weight = cite(aapl_value / total_value * 100, "AAPL Portfolio Weight", formula="aapl_value / total_value * 100", derived_from=["AAPL Position Value", "Total Portfolio Value"])
```

**Aggregate gains/losses:**

```python
total_gain = cite(sum_of_position_gains, "Total Unrealized Gain", formula="sum(position_gains)", derived_from=["AAPL Unrealized Gain", "MSFT Unrealized Gain", "GOOG Unrealized Gain"])
```

**Spending aggregates:**

```python
monthly_spend = cite(sum_of_transactions, "March Groceries Total", formula="sum(grocery_transactions)", derived_from=["Whole Foods 2026-03-02", "Trader Joes 2026-03-09", "Safeway 2026-03-18"])
```

The `derived_from` names must **exactly match** the `name` argument of the parent `cite()` calls. A mismatch silently breaks the derivation chain.

**Save at the end** of your script:

```python
# __cite_setup__
save_citations()
# __cite_setup__
```

**In Python code**, `CitedValue` auto-formats with provenance links. When you use a cited value in an f-string or `print()`, it emits `[value](claim:N)` automatically — do NOT manually wrap or read `citation_id`:

```python
print(f"AAPL is worth ${aapl_value:,.0f}")
# → "AAPL is worth $[45,000](claim:2)"  — $ sits outside the claim pill; fine for display.

# NOTE: Python format specs do NOT accept $ as a prefix. `f"{aapl_value:$,.0f}"` raises ValueError.
# Keep currency/unit symbols outside the Python-emitted claim marker, then if needed
# re-wrap the full display value in the final natural-language response using the claim IDs
# printed by the script. Do not read `citation_id` or construct claim links inside Python.
```

**In your response text**, you MUST include `[value](claim:N)` links for every cited number you present. The claim IDs are visible in the Python script output. This is how the frontend renders clickable pills and applies masking.

Example — after running a script that cited AAPL value (claim:2) and AAPL weight (claim:5):

```
| Ticker | Value | Weight |
|--------|-------|--------|
| AAPL   | [$45,000](claim:2) | [36.0%](claim:5) |

Your AAPL position is worth [$45,000](claim:2), [36.0%](claim:5) of the portfolio.
```

Every private value from a personal-finance tool that appears in your response MUST be wrapped as `[value](claim:N)`, **including every numeric cell inside every markdown table**. Unwrapped private values cannot be masked when sharing.

#### Rules

- When running inline Python with citations, ALWAYS use a PYEOF heredoc: `python3 << 'PYEOF'` ... `PYEOF`
- Call `load_citations()` at the start and `save_citations()` at the end of every script that uses citations
- `# __cite_setup__` markers form exactly two pairs: one around imports/load/metadata at the top, one around `save_citations()` at the bottom — never wrap `cite()` calls, `print()` statements, or analysis code
- Always write `cite()` calls on a single line — never split across multiple lines
- Always call `cite()` directly — do not wrap it in helper functions, aliases, or shorthand (e.g., no `c = cite` or `def c(...): return cite(...)`)
- Cite values you **present to the user** — including every numeric cell in any table you render
- Every derived value must list its `derived_from` parent names
- `source` should match the tool name (e.g. `portfolio_holdings`, `portfolio_summary`, `account_balance`, `transaction_history`, `liabilities`)
- `CitedValue` extends `float` and `CitedStr` extends `str` — they preserve claim markers through arithmetic (`+`, `-`, `*`, `/`, `abs()`, `round()`) and string formatting
- In Python code: do NOT call `float()` or `str()` on cited values before formatting — this strips the claim marker
- In Python code: do NOT read `.citation_id`, `.name`, or any other citation internals from cited objects
- In Python code: do NOT manually wrap in `[text](claim:N)` — `CitedValue.__format__` handles this in print output
- In your response text: ALWAYS wrap cited numbers as `[value](claim:N)` using the IDs from script output
- Skip the citations module for simple lookups with no computation (just use the portfolio page URL citation) — but for anything involving aggregation, weights, ratios, or table rendering, use `cite()` on every value

### Aggregations

For totals, averages, or grouped breakdowns of transactions, holdings, or balances, call the tool with `group_by` / `aggregation` and cite the returned aggregate row directly. Don't sum the underlying values in Python and emit a derived claim with hundreds of parents — backend hard-caps `derived_from` at 8 (first 4 + last 4, matching `finance_analyst`), so any fan-out beyond 8 silently drops the middle entries.

**Correct:**

```python
monthly_spend = cite(category_total_row.amount, "March Groceries Total", source="transaction_history", file=csv_file, row_key="category:groceries", col="Total")
```

**Incorrect:**

```python
monthly_spend = cite(sum(t.amount for t in groceries), "March Groceries Total", formula="sum(grocery_transactions)", derived_from=[t.name for t in groceries])
```

### Preserving Citations in Your Response

When your code outputs `[value](claim:N)` markers, you MUST preserve them in your response text. Reformat the display text for readability but never drop the `[...](claim:N)` wrapper. The claim link must always surround the **full display value** including currency symbols, units, and suffixes.

**Correct:**

```
"Your AAPL position is worth **[$45,000](claim:2)**."
"Portfolio total is **[$1.25M](claim:1)**." — reformatted from [1,250,000](claim:1)
"AAPL is **[36.0%](claim:5)** of your portfolio."
"Your checking balance is [$8,432.19](claim:10)."
"You spent [$412.55](claim:20) on groceries in March."
"Credit card APR: [24.99%](claim:30)."
```

**Incorrect:**

```
"Your AAPL position is worth $45,000." — dropped the citation, value cannot be masked
"Your AAPL position is worth $45,000 [claim:2]." — must use link syntax, not bracket
"Your AAPL position is worth $[45,000](claim:2)." — currency symbol must be inside brackets → [$45,000](claim:2)
"AAPL is [**36.0%**](claim:5) of your portfolio." — markdown inside brackets breaks rendering
"Portfolio total is **$1.25M** (claim:1)." — citation must use link syntax, not bare text
"| AAPL | $45,000 | 36.0% |" — table cells MUST contain `[value](claim:N)` wrappers, not raw values
```

### Gotchas

- `derived_from` names must **exactly match** parent `name` arguments — mismatches silently break the derivation chain
- `source`, `file`, `row_key`, and `col` are required on personal-finance source values for provenance; pass the matching `csv_files` entry as `file`
- Only cite values you present to the user — but in tables and summaries, that means **every cell**, not just the highlights
- Always use f-strings with CitedValue (`f"{value:,.0f}"`) — plain `str()` may not trigger claim formatting
- When formatting cited values for display (e.g. `$X`, `X%`), build the whole display string inside the link via the f-string format, or re-wrap manually in the response: `[$45,000](claim:2)` not `$[45,000](claim:2)` and not `$45,000`
- The full display value including currency/units must be inside the link brackets — `[$45,000](claim:2)` not `$[45,000](claim:2)` and not `[45,000](claim:2)`
- Claim markers are invisible to the user — the frontend renders `[$45,000](claim:2)` as a clean clickable "$45,000" pill with zero visual clutter, even in holdings tables with dozens of rows — never skip claim markers for readability reasons
- **Tables are the #1 failure mode**: raw-value table cells silently break masking. When rendering a holdings/transactions/balances table, every numeric cell (quantity, price, value, weight, gain, APR, balance) MUST be a claim link
- NEVER create `cite()` calls from web search results or from values you invented — they will ALWAYS fail provenance validation because they lack tool-cell provenance
- NEVER write a `.py` file via `apply_patch` and run it with `python3 script.py` for citation work — citation sync is wired into the `bash` tool path and file-run scripts bypass the audit trail. If the heredoc feels too long, split into multiple sequential PYEOF bash calls rather than reaching for `apply_patch`.
- NEVER narrate citation plumbing — do not mention the citations module, `cite()`, `save_citations`, `load_citations`, PYEOF, "I'll cite this", "I need to wrap as claim", or any other mechanics-level description in your thought process or response prose. Talk about _what the numbers mean_, never _how they're cited_.
- For chart-first queries (chart / graph / plot / "show me"), do NOT `curl` + pandas before `visualize` (~60s pre-paint cost). Pass `csv_files[i].url` to `visualize.sources` directly. Compute cited prose metrics (totals, weights, period diffs) after the `visualize` call.

## Detailed Guides

- **website-integration.md** - Backend patterns for serving portfolio data via the external-tool CLI. ONLY read when the user asks to build or edit a website.