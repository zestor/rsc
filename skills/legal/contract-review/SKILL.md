# Contract Review

## Clause Analysis Reference

### Limitation of Liability

**Review**: Cap amount (fixed, fee multiple, uncapped); mutual vs. asymmetric; carveouts from cap; consequential/indirect damages exclusion and its carveouts; per-claim vs. per-year vs. aggregate.
**Red flags**: Cap at fraction of fees on low-value contracts; asymmetric carveouts favoring drafter; broad carveouts that effectively eliminate cap; no consequential damages exclusion for one party.

### Indemnification

**Review**: Mutual vs. unilateral; trigger scope (IP, data breach, bodily injury, rep breach); capped vs. uncapped; procedure (notice, defense control, settlement rights); mitigation duty; relationship to liability cap.
**Red flags**: Unilateral IP indemnification when both parties contribute IP; "any breach" trigger (converts liability cap to uncapped); no defense control right; indefinite survival.

### Intellectual Property

**Review**: Pre-existing IP ownership; IP developed during engagement; work-for-hire scope; license grants (scope, exclusivity, territory, sublicensing); open source; feedback clauses.
**Red flags**: Broad IP assignment capturing customer pre-existing IP; work-for-hire beyond deliverables; unrestricted perpetual feedback licenses; license scope exceeding business need.

### Data Protection

**Review**: DPA requirement; controller vs. processor classification; sub-processor rights; breach notification timeline; cross-border transfer mechanisms; deletion/return on termination; audit rights; purpose limitation.
**Red flags**: No DPA when personal data is processed; blanket sub-processor authorization; breach notification exceeding regulatory timeline; no cross-border protections; inadequate deletion provisions.

### Term and Termination

**Review**: Initial and renewal terms; auto-renewal notice periods; termination for convenience (availability, notice, fees); termination for cause (cure period, triggers); effects (data return, transition assistance, survival).
**Red flags**: Long terms with no convenience termination; auto-renewal with short notice windows (30 days for annual); no cure period; inadequate transition assistance; indefinite survival clauses.

### Governing Law and Dispute Resolution

**Review**: Choice of law; mechanism (litigation, arbitration, mediation); venue; arbitration rules and seat; jury waiver; class action waiver; prevailing party fees.
**Red flags**: Unusual or remote venue; mandatory arbitration with drafter-favorable rules; jury waiver without corresponding protections; no escalation process.

## Deviation Classification

| Level      | Criteria                                                                           | Action                                                                                |
| ---------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| **GREEN**  | Aligns with or exceeds standard position; commercially reasonable minor variations | Note for awareness                                                                    |
| **YELLOW** | Outside standard position but within negotiable market range                       | Generate redline with fallback position; estimate business impact                     |
| **RED**    | Outside acceptable range; material risk; triggers escalation                       | Explain specific risk; provide market-standard alternative; recommend escalation path |

## Negotiation Priority Tiers

| Tier | Label         | Description                                                                                                 | Strategy                                    |
| ---- | ------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| 1    | Must-Haves    | Uncapped/insufficient liability; missing data protection; IP jeopardizing core assets; regulatory conflicts | Never concede without escalation            |
| 2    | Should-Haves  | Liability cap adjustments; indemnification scope; termination flexibility; audit rights                     | Negotiate firmly; trade Tier 3 to win here  |
| 3    | Nice-to-Haves | Preferred governing law; notice period preferences; minor definitional improvements; insurance certs        | Concession candidates to secure Tier 2 wins |

## Gotchas

- **Indemnification and liability cap interact** -- an uncapped indemnity can render the liability cap meaningless; always read these two clauses together, not in isolation.
- **Auto-renewal notice windows are traps** -- a 30-day notice period on an annual auto-renewal means missing the window by one day locks the org into another full year.
- **"Fees paid" caps shrink over time** -- a liability cap tied to "fees paid in the prior 12 months" on a declining-usage contract can approach zero, leaving effectively no cap.
- **Survival clauses can extend obligations indefinitely** -- boilerplate "the following sections survive termination" without a time limit can create perpetual obligations that outlive the commercial relationship.
- **Work-for-hire only applies to specific categories** -- under US copyright law, work-for-hire applies only to nine statutory categories; if deliverables fall outside those categories, an explicit assignment clause is required or the vendor retains ownership.