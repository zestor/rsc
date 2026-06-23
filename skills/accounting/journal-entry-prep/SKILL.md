# Journal Entry Preparation

Standard entry types, approval thresholds, and common errors for month-end journal entries.

## Standard Entry Types

| Entry Type               | Debit                               | Credit                   | Key Detail                                                               |
| ------------------------ | ----------------------------------- | ------------------------ | ------------------------------------------------------------------------ |
| **AP accrual**           | Expense (or asset if capitalizable) | Accrued liabilities      | Auto-reverse next period; base on POs, contracts, or historical run-rate |
| **Depreciation**         | Depreciation expense (by dept)      | Accumulated depreciation | Run from FA register; verify new additions have correct life/method      |
| **Prepaid amortization** | Expense (insurance, software, etc.) | Prepaid expense          | Maintain schedule with start/end dates and monthly amounts               |
| **Salary accrual**       | Salary expense (by dept)            | Accrued payroll          | Calculate based on working days in period vs pay period                  |
| **Bonus accrual**        | Bonus expense (by dept)             | Accrued bonus            | Reflect plan terms: targets, performance metrics, payout timing          |
| **Payroll tax accrual**  | Payroll tax expense                 | Accrued payroll taxes    | Include FICA, FUTA, state taxes, employer benefits, 401k match           |
| **Revenue recognition**  | Deferred revenue (or AR)            | Revenue                  | Follow ASC 606 five-step model; maintain contract-level detail           |
| **Deferred revenue**     | Cash / AR                           | Deferred revenue         | Payment received before performance obligation satisfied                 |

## Approval Matrix

| Entry Type                | Threshold    | Approver            |
| ------------------------- | ------------ | ------------------- |
| Standard recurring        | Any amount   | Accounting manager  |
| Non-recurring / manual    | < $50K       | Accounting manager  |
| Non-recurring / manual    | $50K - $250K | Controller          |
| Non-recurring / manual    | > $250K      | CFO / VP Finance    |
| Top-side / consolidation  | Any amount   | Controller or above |
| Out-of-period adjustments | Any amount   | Controller or above |

## ASC 606 Five-Step Framework

1. Identify the contract with a customer
2. Identify distinct performance obligations
3. Determine transaction price (including variable consideration)
4. Allocate transaction price to performance obligations
5. Recognize revenue as/when each obligation is satisfied

## Common Errors

| Error                            | How It Manifests                                                    |
| -------------------------------- | ------------------------------------------------------------------- |
| Missing reversal                 | Accrual not set to auto-reverse -> double-counted next period       |
| Wrong period                     | Entry posted to closed or incorrect period                          |
| Wrong sign                       | Debit entered as credit or vice versa                               |
| Duplicate entry                  | Same transaction recorded twice                                     |
| Stale accrual                    | Recurring accrual not updated for changed circumstances             |
| Missing intercompany elimination | Entries between entities without corresponding elimination          |
| Capitalization error             | Expense that should be capitalized, or vice versa                   |
| Cut-off error                    | Transaction recorded in wrong period based on delivery/service date |
| Incorrect FX rate                | Foreign currency entry using wrong rate or date                     |
| Round-number estimate            | Suspiciously round amount that doesn't reflect actual calculation   |

## Gotchas

- **Auto-reversal timing matters** -- if the reversal posts on the first day of the next month but the replacement entry posts mid-month, the interim balance is wrong for anyone pulling data between those dates.
- **PTO accruals vary by jurisdiction** -- some states (e.g., California) treat PTO as earned wages that cannot expire; the liability must accrue continuously regardless of company policy.
- **Bonus accruals need quarterly true-ups** -- booking 1/12th of the annual target each month ignores changing performance metrics; true up to actual attainment quarterly.
- **Prepaid thresholds prevent clutter** -- items below a materiality threshold (often $5K-$10K) should be expensed outright rather than added to the prepaid schedule.
- **Out-of-period entries need extra disclosure** -- entries correcting prior periods require controller approval and may trigger restatement evaluation under ASC 250.