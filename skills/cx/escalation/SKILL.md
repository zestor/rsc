# Escalation

Determine when and how to escalate support issues. Structure briefs that give receiving teams everything they need to act.

## Escalate vs. Handle in Support

**Handle in support when:** documented solution exists, configuration/setup issue you can resolve, customer needs guidance not a fix, known limitation with documented alternative.

**Escalate when:**

- **Technical**: Confirmed bug needing code fix, infrastructure investigation, data corruption/loss
- **Impact**: Multiple customers affected, production down, data integrity at risk, security concern
- **Business**: High-value customer at risk, SLA breach imminent/occurred, customer requesting executive involvement
- **Pattern**: Same issue from 3+ customers, recurring issue supposedly fixed, increasing severity

## Escalation Tiers

| From                 | To                 | When                                                                                      |
| -------------------- | ------------------ | ----------------------------------------------------------------------------------------- |
| **L1 → L2**          | Senior support     | Deeper investigation, specialized product knowledge                                       |
| **L2 → Engineering** | Engineering team   | Confirmed bug, infrastructure issue, needs code change                                    |
| **L2 → Product**     | Product management | Feature gap causing pain, design decision needed                                          |
| **Any → Security**   | Security team      | Data exposure, unauthorized access, vulnerability, compliance — **bypasses normal tiers** |
| **Any → Leadership** | Exec team          | High-revenue churn risk, SLA breach on critical account, PR/legal risk                    |

## Escalation Format

```
ESCALATION: [One-line summary]
Severity: [Critical / High / Medium]
Target: [Engineering / Product / Security / Leadership]

IMPACT
- Customers affected: [Number and names]
- Workflow impact: [What's broken]
- Revenue at risk: [If applicable]
- SLA status: [Within / At risk / Breached]

ISSUE DESCRIPTION
[3-5 sentences: what's happening, when it started, scope]

REPRODUCTION STEPS (for bugs)
1. [Step]
2. [Step]
Expected: [X]  Actual: [Y]
Environment: [Details]

WHAT'S BEEN TRIED
1. [Action] → [Result]

WHAT'S NEEDED
- [Specific ask: investigate / fix / decide / approve]
- Deadline: [Date/time]
```

## Business Impact Dimensions

| Dimension       | What to Quantify                            |
| --------------- | ------------------------------------------- |
| **Breadth**     | How many customers/users affected? Growing? |
| **Depth**       | Blocked vs. inconvenienced?                 |
| **Duration**    | How long? How long until critical?          |
| **Revenue**     | ARR at risk? Pending deals affected?        |
| **Reputation**  | Could become public? Reference customer?    |
| **Contractual** | SLAs breached? Contractual obligations?     |

## Follow-up Cadence

| Severity     | Internal Check | Customer Update         |
| ------------ | -------------- | ----------------------- |
| **Critical** | Every 2hr      | Every 2-4hr             |
| **High**     | Every 4hr      | Every 4-8hr             |
| **Medium**   | Daily          | Every 1-2 business days |

Don't escalate and forget — maintain ownership of the customer relationship.

## Gotchas

- **Reproduction steps are the #1 thing engineering needs** — vague escalations get deprioritized. Start from a clean state, use exact values, note frequency.
- **"Investigate" vs "fix" vs "decide" are different asks** — be explicit about what you need.
- **Update even when there's no news** — "still investigating, here's what we know" beats silence. Silence looks like you forgot.
- **De-escalate when warranted** — if root cause turns out to be support-resolvable or a workaround unblocks the customer, update severity and notify the receiving team.