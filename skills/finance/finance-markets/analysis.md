# Financial Analysis Guide

Before calling any finance tool, you **must** call `describe_external_tools(source_id="finance", tool_names=[...])` — the system enforces this.

## Fetching Financial Statements

### Statement Types

| Type            | Contains                                   |
| --------------- | ------------------------------------------ |
| `income`        | Revenue, expenses, net income, EPS         |
| `balance_sheet` | Assets, liabilities, equity                |
| `cash_flow`     | Operating, investing, financing cash flows |

### Basic Request

```python
# 5-year DCF inputs: revenue, net income, D&A, SBC, operating CF, capex
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period": "annual",
    "as_of_fiscal_year": 2025,
    "limit": 5,
    "income_statement_metrics": ["income_statement_total_revenues", "income_statement_consolidated_net_income", "income_statement_depreciation_and_amortization_expenses"],
    "cash_flow_metrics": ["cash_flow_statement_share_based_compensation_expense", "cash_flow_statement_cash_from_operating_activities", "cash_flow_statement_purchases_of_property_plant_and_equipment"]
})
```

### Period Formats

- Annual: `"2024"`, `"2023"`
- Quarterly: `"2024-Q1"`, `"2024-Q2"`
- TTM (trailing twelve months): `"TTM"`

## Ratio Analysis

### Profitability Ratios

Calculate from income statement and balance sheet:

```
Gross Margin = Gross Profit / Revenue
Operating Margin = Operating Income / Revenue
Net Margin = Net Income / Revenue
ROE = Net Income / Shareholders Equity
ROA = Net Income / Total Assets
ROIC = NOPAT / Invested Capital
```

### Liquidity Ratios

```
Current Ratio = Current Assets / Current Liabilities
Quick Ratio = (Current Assets - Inventory) / Current Liabilities
Cash Ratio = Cash / Current Liabilities
```

### Leverage Ratios

```
Debt-to-Equity = Total Debt / Shareholders Equity
Debt-to-EBITDA = Total Debt / EBITDA
Interest Coverage = EBIT / Interest Expense
```

### Calculating Ratios

Fetch the required metrics via `finance_company_financials`, then calculate ratios locally. Always cite derived values with `formula` and `derived_from`:

```python
# Apple ROE (fetch net income and equity, compute net_income / equity)
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period": "annual",
    "as_of_fiscal_year": 2025,
    "limit": 1,
    "income_statement_metrics": ["income_statement_consolidated_net_income"],
    "balance_sheet_metrics": ["balance_sheet_total_shareholders_equity"]
})
```

```python
# Cite source values from the returned data
net_income = cite(row["income_statement_consolidated_net_income"], "AAPL FY2024 Net Income", source="finance_company_financials", file=csv_file, row_key="2024-Q4", col="income_statement_consolidated_net_income")
equity = cite(row["balance_sheet_total_shareholders_equity"], "AAPL FY2024 Equity", source="finance_company_financials", file=csv_file, row_key="2024-Q4", col="balance_sheet_total_shareholders_equity")

# Cite the derived ratio
roe = cite(net_income / equity * 100, "AAPL FY2024 ROE", formula="net_income / equity * 100", derived_from=["AAPL FY2024 Net Income", "AAPL FY2024 Equity"])
```

## Comparable Company Analysis

### Step 1: Identify Peer Group

Identify peer companies based on sector and size (screener is currently unavailable).
Use domain knowledge or external research to select comparable tickers.

### Step 2: Fetch Valuation Multiples

Use `finance_quotes` only when the reference date is today. For past reference dates, use `finance_ohlcv_histories` for price data and `finance_company_financials` for EPS/market cap.

```python
# Valuation snapshot
await call_external_tool(tool_name="finance_quotes", source_id="finance", arguments={
    "ticker_symbols": ["AAPL", "MSFT", "GOOGL"],
    "fields": ["price", "marketCap", "pe", "eps", "dividendYieldTTM"]
})
```

### Step 3: Fetch Growth Metrics

```python
# Peer group 3-year revenue comparison
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL", "MSFT", "GOOGL", "META"],
    "period": "annual",
    "as_of_fiscal_year": 2025,
    "limit": 3,
    "income_statement_metrics": ["income_statement_total_revenues"]
})
```

```python
# Cite each company's revenue, then derive growth
rev_2024 = cite(row_2024["income_statement_total_revenues"], "AAPL FY2024 Revenue", source="finance_company_financials", file=csv_file, row_key="2024-Q4", col="income_statement_total_revenues")
rev_2023 = cite(row_2023["income_statement_total_revenues"], "AAPL FY2023 Revenue", source="finance_company_financials", file=csv_file, row_key="2023-Q4", col="income_statement_total_revenues")
growth = cite((rev_2024 - rev_2023) / rev_2023 * 100, "AAPL Revenue Growth YoY", formula="(rev_2024 - rev_2023) / rev_2023 * 100", derived_from=["AAPL FY2024 Revenue", "AAPL FY2023 Revenue"])
```

### Common Multiples

| Multiple  | Formula                   | Best For                     |
| --------- | ------------------------- | ---------------------------- |
| P/E       | Price / EPS               | Profitable companies         |
| EV/EBITDA | Enterprise Value / EBITDA | Capital-intensive businesses |
| P/S       | Price / Revenue per Share | High-growth, unprofitable    |
| P/B       | Price / Book Value        | Asset-heavy (banks, REITs)   |
| PEG       | P/E / EPS Growth Rate     | Growth-adjusted valuation    |

## DCF Valuation

### Required Inputs

1. **Free Cash Flow projection** - from historical cash flow statements
2. **Discount rate (WACC)** - calculate or use industry average
3. **Terminal growth rate** - typically 2-3% (GDP growth)
4. **Projection period** - typically 5-10 years

### Workflow

```python
# 5-year DCF inputs: revenue, net income, D&A, SBC, operating CF, capex
await call_external_tool(tool_name="finance_company_financials", source_id="finance", arguments={
    "ticker_symbols": ["AAPL"],
    "period": "annual",
    "as_of_fiscal_year": 2025,
    "limit": 5,
    "income_statement_metrics": ["income_statement_total_revenues", "income_statement_consolidated_net_income", "income_statement_depreciation_and_amortization_expenses"],
    "cash_flow_metrics": ["cash_flow_statement_share_based_compensation_expense", "cash_flow_statement_cash_from_operating_activities", "cash_flow_statement_purchases_of_property_plant_and_equipment"]
})
```

```python
# 2. Cite source values and calculate FCF
op_cf = cite(row["cash_flow_statement_cash_from_operating_activities"], "AAPL FY2024 Operating CF", source="finance_company_financials", file=csv_file, row_key="2024-Q4", col="cash_flow_statement_cash_from_operating_activities")
capex = cite(row["cash_flow_statement_purchases_of_property_plant_and_equipment"], "AAPL FY2024 CapEx", source="finance_company_financials", file=csv_file, row_key="2024-Q4", col="cash_flow_statement_purchases_of_property_plant_and_equipment")
fcf = cite(op_cf - capex, "AAPL FY2024 FCF", formula="op_cf - capex", derived_from=["AAPL FY2024 Operating CF", "AAPL FY2024 CapEx"])

# 3. Project future FCF (use growth assumptions)

# 4. Calculate present value locally
# wacc = 0.10
# fcf_projections = [10e9, 11e9, 12e9, 13e9, 14e9]
# terminal_value = 200e9
# pv = sum(fcf / (1 + wacc)**i for i, fcf in enumerate(fcf_projections, 1))
# pv += terminal_value / (1 + wacc)**5
```

### Terminal Value

Gordon Growth Model:

```
Terminal Value = FCF_final * (1 + g) / (r - g)
```

Where:

- `g` = perpetual growth rate (2-3%)
- `r` = discount rate (WACC)

## Statistical Analysis

For statistical analysis, fetch price history via `finance_ohlcv_histories` and perform calculations locally:

```python
# Correlation analysis data
await call_external_tool(tool_name="finance_ohlcv_histories", source_id="finance", arguments={
    "ticker_symbols": ["AAPL", "MSFT"],
    "query": "AAPL and MSFT price correlation",
    "start_date_yyyy_mm_dd": "2024-01-01",
    "end_date_yyyy_mm_dd": "2024-12-31",
    "fields": ["close"]
})
```

```python
# 2. Calculate and cite derived metrics:
import numpy as np

returns = df["close"].pct_change().dropna()
vol = returns.std() * np.sqrt(252)
annualized_vol = cite(vol * 100, "AAPL Annualized Volatility", formula="std(daily_returns) * sqrt(252) * 100", derived_from=["AAPL Daily Returns"])

# Beta: covariance(stock, benchmark) / variance(benchmark)
# Correlation between assets
# Sharpe ratio
```

**Common analyses:**

- Correlation between assets
- Beta calculation (regression vs benchmark)
- Sharpe ratio
- Portfolio variance
- Moving averages and technical indicators
