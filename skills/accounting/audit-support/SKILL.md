# Audit Support

SOX 404 control testing methodology, sample selection, deficiency classification, and control type reference.

## Assertions by Account Type

| Account Type              | Key Assertions                              |
| ------------------------- | ------------------------------------------- |
| Revenue                   | Occurrence, Completeness, Accuracy, Cut-off |
| Accounts Receivable       | Existence, Valuation (allowance), Rights    |
| Inventory                 | Existence, Valuation, Completeness          |
| Fixed Assets              | Existence, Valuation, Completeness, Rights  |
| Accounts Payable          | Completeness, Accuracy, Existence           |
| Accrued Liabilities       | Completeness, Valuation, Accuracy           |
| Equity                    | Completeness, Accuracy, Presentation        |
| Financial Close/Reporting | Presentation, Accuracy, Completeness        |

## Sample Size Guidance

| Control Frequency      | Expected Population | Low Risk | Moderate Risk | High Risk |
| ---------------------- | ------------------- | -------- | ------------- | --------- |
| Annual                 | 1                   | 1        | 1             | 1         |
| Quarterly              | 4                   | 2        | 2             | 3         |
| Monthly                | 12                  | 2        | 3             | 4         |
| Weekly                 | 52                  | 5        | 8             | 15        |
| Daily                  | ~250                | 20       | 30            | 40        |
| Per-transaction (<250) | <250                | 20       | 30            | 40        |
| Per-transaction (250+) | 250+                | 25       | 40            | 60        |

Increase sample size when: control is the sole control for a risk, prior deficiency was found, control is new, or external auditor is relying on management testing.

## Deficiency Classification

| Level                      | Definition                                                                             | Indicators                                                                                                                                                |
| -------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Deficiency**             | Control design/operation doesn't allow timely prevention or detection of misstatements | Low likelihood, compensating controls may mitigate                                                                                                        |
| **Significant Deficiency** | Less severe than material weakness but merits governance attention                     | Misstatement more than inconsequential but less than material; key control not fully mitigated                                                            |
| **Material Weakness**      | Reasonable possibility a material misstatement won't be prevented/detected timely      | Senior management fraud (any magnitude), restatement of prior financials, auditor-identified material misstatement, ineffective audit committee oversight |

Aggregate individually minor deficiencies in the same process or assertion -- combined effect may be significant or material.

## Control Types

| Type                    | Key Testing Approach                                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Automated**           | Test system config once per period (if ITGCs over change management are effective)                                 |
| **Manual**              | Test via inspection, observation, re-performance; verify right person, timeliness, evidence of review              |
| **IT-Dependent Manual** | Test the manual control AND the completeness/accuracy of the underlying report (IPE testing)                       |
| **Entity-Level**        | Can reduce process-level testing extent but typically cannot replace it; ineffective ELCs are strong MW indicators |

## Evidence Standards

**Sufficient:** screenshots of system controls, signed approvals, email approvals with identifiable approver/date, system audit logs, re-performed calculations, dated observation notes.

**Insufficient:** verbal confirmations alone, undated documents, evidence without identifiable performer, generic reports without timestamps, "per discussion with [name]" without corroboration.

## Gotchas

- **IPE testing is frequently missed** -- when a reviewer relies on a system-generated report, you must test the completeness and accuracy of that report, not just the review itself.
- **One automated control test is not always enough** -- if change management ITGCs failed or system config changed mid-period, re-test the automated control after the change.
- **Aggregation changes the picture** -- three individually minor deficiencies in the same revenue process can aggregate to a significant deficiency or material weakness.
- **"Inquiry alone" is never sufficient** -- PCAOB standards require corroborating evidence even when management provides verbal explanations.
- **Scoping misses qualitative factors** -- an account below the quantitative materiality threshold can still be significant if it involves fraud risk, complex estimates, or related-party transactions.