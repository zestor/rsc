# Close Management

Task sequencing, dependency map, and status tracking for the month-end close.

## Month-End Close Checklist

### Pre-Close (Last 2-3 Business Days)

- [ ] Send close calendar and deadline reminders to all contributors
- [ ] Confirm cut-off procedures with AP, AR, payroll, and treasury
- [ ] Verify all sub-systems processing normally (ERP, payroll, banking)
- [ ] Complete preliminary bank reconciliation (all but last-day activity)
- [ ] Review open POs for potential accrual needs
- [ ] Confirm payroll schedule aligns with close timeline

### Day 1 (T+1)

- [ ] Confirm all sub-ledger modules completed period-end processing
- [ ] Run AP accruals for goods/services received but not invoiced
- [ ] Post payroll entries and payroll accrual
- [ ] Record cash receipts and disbursements through month-end
- [ ] Post intercompany transactions and confirm with counterparties
- [ ] Complete bank reconciliation with final statement
- [ ] Run fixed asset depreciation and prepaid amortization

### Day 2 (T+2)

- [ ] Complete revenue recognition and deferred revenue adjustments
- [ ] Post all remaining accrual journal entries
- [ ] Complete AR and AP subledger reconciliations
- [ ] Record inventory adjustments (if applicable)
- [ ] Post FX revaluation entries
- [ ] Begin balance sheet account reconciliations

### Day 3 (T+3)

- [ ] Complete all balance sheet reconciliations
- [ ] Post adjusting entries identified during reconciliation
- [ ] Complete intercompany reconciliation and elimination entries
- [ ] Run preliminary trial balance and income statement
- [ ] Perform preliminary flux analysis; investigate material variances

### Day 4 (T+4)

- [ ] Post tax provision entries (income, sales, property)
- [ ] Complete equity roll-forward (stock comp, treasury stock)
- [ ] Finalize all journal entries — soft close
- [ ] Generate draft financial statements (P&L, BS, CF)
- [ ] Detailed flux analysis and variance explanations
- [ ] Management review of financials and key metrics

### Day 5 (T+5)

- [ ] Post final adjustments from management review
- [ ] Finalize financial statements — hard close
- [ ] Lock the period in ERP/GL
- [ ] Distribute financial reporting package
- [ ] Update forecasts based on actuals
- [ ] Conduct close retrospective

## Task Dependency Map

```
LEVEL 1 (No dependencies — start at T+1):
├── Cash receipts/disbursements recording
├── Bank statement retrieval
├── Payroll processing/accrual
├── Fixed asset depreciation run
├── Prepaid amortization
├── AP accrual preparation
└── Intercompany transaction posting

LEVEL 2 (Depends on Level 1):
├── Bank reconciliation (needs: cash entries + bank statement)
├── Revenue recognition (needs: billing/delivery data finalized)
├── AR subledger reconciliation (needs: all revenue/cash entries)
├── AP subledger reconciliation (needs: all AP entries/accruals)
├── FX revaluation (needs: all foreign currency entries posted)
└── Remaining accrual JEs (needs: review of all source data)

LEVEL 3 (Depends on Level 2):
├── All balance sheet reconciliations (needs: all JEs posted)
├── Intercompany reconciliation (needs: both sides posted)
├── Adjusting entries from reconciliations
└── Preliminary trial balance

LEVEL 4 (Depends on Level 3):
├── Tax provision (needs: pre-tax income finalized)
├── Equity roll-forward
├── Consolidation and eliminations
├── Draft financial statements
└── Preliminary flux analysis

LEVEL 5 (Depends on Level 4):
├── Management review
├── Final adjustments
├── Hard close / period lock
├── Financial reporting package
└── Forecast updates
```

Critical path: Cash/AP/AR entries -> Subledger recs -> BS recs -> Tax provision -> Draft financials -> Management review -> Hard close.

## 5-Day vs 3-Day Close

| Day     | Standard (5-Day)                                                                  | Accelerated (3-Day)                                                            |
| ------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **T+1** | Level 1 entries: cash, payroll, AP accruals, depreciation, prepaids, intercompany | All JEs posted, all subledger recs, bank rec, intercompany rec, preliminary TB |
| **T+2** | Revenue rec, remaining accruals, subledger recs, FX reval                         | All BS recs, tax provision, consolidation, draft financials, flux, mgmt review |
| **T+3** | BS recs, intercompany rec, eliminations, preliminary TB, flux                     | Final adjustments, hard close, reporting package                               |
| **T+4** | Tax provision, equity roll-forward, draft financials, detailed flux, mgmt review  | --                                                                             |
| **T+5** | Final adjustments, hard close, period lock, reporting package                     | --                                                                             |

3-day close prerequisites: automated recurring JEs, continuous monthly reconciliation, automated intercompany elimination, pre-close activities done before month-end, real-time sub-system integration.

## Close Metrics

| Metric                              | Target           |
| ----------------------------------- | ---------------- |
| Close duration (business days)      | Reduce over time |
| Adjusting entries after soft close  | Minimize         |
| Late tasks (past deadline)          | Zero             |
| Reconciliation exceptions           | Reduce over time |
| Post-close restatements/corrections | Zero             |

## Common Bottlenecks

| Bottleneck                    | Solution                                                         |
| ----------------------------- | ---------------------------------------------------------------- |
| Late AP accruals              | Continuous accrual estimation; firm cut-off deadlines            |
| Manual recurring JEs          | Automate standard entries in ERP                                 |
| Slow reconciliations          | Continuous/rolling reconciliation during the month               |
| Intercompany delays           | Automated matching; stricter counterparty deadlines              |
| Large mgmt review adjustments | Improve preliminary review; empower team to catch issues earlier |

## Gotchas

- **Dependencies are the bottleneck, not individual tasks** -- parallel-processing independent Level 1 and Level 2 tasks matters more than speeding up any single task.
- **Pre-close is where time is actually saved** -- completing cut-off procedures, preliminary bank recs, and accrual estimates before month-end compresses the critical path more than anything post-close.
- **Soft close is not optional** -- skipping the soft close to save a day usually backfires with larger adjustments during management review.
- **Intercompany is the most common blocker** -- one entity posting late cascades to consolidation, eliminations, and financials for all entities.
- **Recurring accruals drift** -- auto-reversed accruals re-booked at the same amount each month mask changes in underlying costs; review amounts quarterly.