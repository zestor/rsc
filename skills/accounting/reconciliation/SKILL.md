# Reconciliation

Reconciliation types, reconciling item categorization, aging thresholds, and escalation rules.

## Reconciliation Types

| Type                | Compare                                                                            | Common Difference Causes                                                                                                 |
| ------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **GL to Subledger** | GL control account vs subledger detail (AR, AP, FA, inventory, prepaids, accruals) | Manual JEs to control account not in subledger, pending interfaces, batch timing, reclasses without subledger adjustment |
| **Bank**            | GL cash balance vs bank statement balance                                          | Outstanding checks, deposits in transit, unrecorded bank fees/interest, recording errors                                 |
| **Intercompany**    | Entity A receivable from B vs Entity B payable to A                                | One-sided recording, different FX rates, misclassification, disputed amounts, different cut-off practices                |

## Bank Reconciliation Format

```
Balance per bank statement:         $XX,XXX
  + Deposits in transit              $X,XXX
  - Outstanding checks             ($X,XXX)
  +/- Bank errors                    $X,XXX
Adjusted bank balance:              $XX,XXX

Balance per general ledger:         $XX,XXX
  + Interest/credits not recorded    $X,XXX
  - Bank fees not recorded         ($X,XXX)
  +/- GL errors                      $X,XXX
Adjusted GL balance:                $XX,XXX

Difference:                         $0.00
```

## Common Reconciling Items

**Bank side:** outstanding checks, deposits in transit, bank errors, electronic debits not yet recorded.
**Book side:** unrecorded bank fees, unrecorded interest income, NSF/returned checks, GL posting errors, duplicate entries.

## Reconciling Item Categories

| Category                   | Examples                                                                                                        | Action                                                   |
| -------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **Timing differences**     | Outstanding checks, deposits in transit, pending interfaces, pending approvals                                  | Monitor only -- clears within 1-5 business days          |
| **Adjustments required**   | Unrecorded bank fees, unrecorded interest, recording errors, missing entries, classification errors             | Prepare adjusting JE                                     |
| **Requires investigation** | Unidentified differences, disputed items, aged items past expected clearance, recurring unexplained differences | Investigate root cause, document, escalate if unresolved |

## Aging Thresholds

| Age        | Status  | Action                                                       |
| ---------- | ------- | ------------------------------------------------------------ |
| 0-30 days  | Current | Monitor                                                      |
| 31-60 days | Aging   | Investigate why item has not cleared                         |
| 61-90 days | Overdue | Escalate to supervisor; document investigation               |
| 90+ days   | Stale   | Escalate to management; evaluate for write-off or adjustment |

## Escalation Triggers

| Trigger                         | Threshold | Escalation                               |
| ------------------------------- | --------- | ---------------------------------------- |
| Individual item > $10K          | $10K      | Supervisor review                        |
| Individual item > $50K          | $50K      | Controller review                        |
| Total reconciling items > $100K | $100K     | Controller review                        |
| Item age > 60 days              | 60 days   | Supervisor follow-up                     |
| Item age > 90 days              | 90 days   | Controller / management review           |
| Growing trend 3+ periods        | 3 periods | Process improvement investigation        |
| Unreconciled difference         | Any       | Cannot close -- must resolve or document |

## Gotchas

- **Segregation of duties** -- the person reconciling an account should not be the same person processing transactions in it; this is a SOX control point auditors specifically test.
- **Carrying items forward is not resolving them** -- reconciling items copied from prior months without investigation create a growing balance that eventually becomes material.
- **GL-to-subledger differences often indicate manual JEs** -- if someone posted directly to the GL control account (e.g., a top-side adjustment), the subledger won't reflect it, and the rec will break until traced.
- **Bank rec timing items that don't clear in 5 days aren't timing items** -- an outstanding check older than 30 days likely indicates a stale check or lost payment requiring investigation, not normal float.
- **Intercompany FX differences are normal but must be quantified** -- if entities use different rates, the difference is real and must be booked to an FX gain/loss account during elimination, not left as a reconciling item.