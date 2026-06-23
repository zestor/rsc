# Financial Statements

Standard formats, GAAP presentation requirements, and common adjustments for the three primary financial statements.

## Income Statement (ASC 220 / IAS 1)

Standard line items: Revenue (product, service, other) -> Cost of Revenue -> **Gross Profit** -> Operating Expenses (R&D, S&M, G&A) -> **Operating Income** -> Other Income/Expense (interest, other) -> **Pre-Tax Income** -> Tax Expense -> **Net Income** -> EPS (basic, diluted).

Key GAAP rules:

- Classify expenses by function (US standard) or by nature; if by function, disclose depreciation/amortization and employee benefit costs by nature in notes
- Discontinued operations presented separately, net of tax
- Extraordinary items prohibited under both US GAAP and IFRS
- Revenue disaggregated per ASC 606 (nature, timing, uncertainty)
- SBC classified within functional expense categories with total disclosed in notes

## Balance Sheet (ASC 210 / IAS 1)

Standard ordering: **Assets** (current then non-current, most liquid first) -> **Liabilities** (current then non-current) -> **Stockholders' Equity**.

Key GAAP rules:

- Current = realized/settled within 12 months (or operating cycle if longer)
- AR shown net of allowance for credit losses (ASC 326)
- PP&E shown net of accumulated depreciation
- Goodwill not amortized -- annual impairment test (ASC 350)
- ROU assets and lease liabilities recognized for operating and finance leases (ASC 842)

## Cash Flow Statement (ASC 230 / IAS 7)

Indirect method (most common): Net Income -> adjust for non-cash items (D&A, SBC, deferred taxes, impairments, gains/losses) -> changes in operating assets and liabilities -> **Operating Cash Flow** -> Investing activities (capex, acquisitions, investments) -> Financing activities (debt, equity, dividends) -> FX effect -> **Net Change in Cash**.

Key GAAP rules:

- Interest paid and income taxes paid must be disclosed (face or notes)
- Non-cash investing/financing activities disclosed separately (e.g., lease assets, stock-for-acquisition)
- Cash equivalents = original maturity of 3 months or less

## Common Period-End Adjustments

| Adjustment                            | Entry Pattern                                       |
| ------------------------------------- | --------------------------------------------------- |
| Accruals (AP, payroll, interest)      | Dr Expense, Cr Accrued Liability                    |
| Deferrals (prepaid, deferred revenue) | Dr Expense/Deferred Rev, Cr Prepaid/Revenue         |
| Depreciation & amortization           | Dr D&A Expense, Cr Accumulated D&A                  |
| Bad debt provision                    | Dr Bad Debt Expense, Cr Allowance for Credit Losses |
| Inventory write-down                  | Dr COGS/Loss, Cr Inventory                          |
| FX revaluation                        | Dr/Cr FX Gain/Loss, Cr/Dr Monetary Asset/Liability  |
| Tax provision                         | Dr Tax Expense, Cr Tax Payable / Deferred Tax       |
| Fair value mark-to-market             | Dr/Cr Unrealized Gain/Loss, Cr/Dr Investment        |

## Flux Analysis Thresholds

| Line Item Size | Dollar Threshold | Percentage Threshold |
| -------------- | ---------------- | -------------------- |
| > $10M         | $500K            | 5%                   |
| $1M - $10M     | $100K            | 10%                  |
| < $1M          | $50K             | 15%                  |

Trigger investigation when either threshold is exceeded. Decompose into: volume, price, mix, new/discontinued items, one-time items, timing, and currency effects.

## Gotchas

- **Current portion of long-term debt** -- reclassify debt maturing within 12 months to current liabilities; frequently missed when refinancing terms change.
- **Intercompany elimination gaps** -- eliminations must cover revenue, COGS, receivables, and payables; partial elimination creates asymmetric consolidation errors.
- **Operating vs finance lease classification** -- misclassifying leases under ASC 842 affects both the balance sheet (ROU asset/liability split) and the income statement (rent expense vs depreciation + interest).
- **Non-GAAP reconciliation requirement** -- presenting non-GAAP measures (common in earnings releases) without a clear reconciliation to GAAP violates SEC guidance.
- **Cash flow classification of interest** -- US GAAP requires interest paid in operating activities; IFRS allows operating or financing, creating comparability issues for dual-reporters.