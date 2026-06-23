# Ticket Triage

Categorize, prioritize (P1-P4), and route incoming support tickets.

## Category Taxonomy

Assign a **primary category** and optionally a **secondary category**:

| Category            | Description                                            |
| ------------------- | ------------------------------------------------------ |
| **Bug**             | Product behaving incorrectly or unexpectedly           |
| **How-to**          | Customer needs guidance on using the product           |
| **Feature request** | Customer wants a capability that doesn't exist         |
| **Billing**         | Payment, subscription, invoice, or pricing issues      |
| **Account**         | Account access, permissions, settings, user management |
| **Integration**     | Issues connecting to third-party tools or APIs         |
| **Security**        | Security concerns, data access, compliance questions   |
| **Data**            | Data quality, migration, import/export issues          |
| **Performance**     | Speed, reliability, or availability issues             |

## Category Gotchas

- If the customer reports **both** a bug and a feature request, the bug is primary
- "It used to work and now it doesn't" = **Bug**, not Feature request
- Can't log in due to a bug = **Bug**, not Account — root cause drives category
- When in doubt, lean toward **Bug** — better to investigate than dismiss

## Priority Framework

| Priority          | Criteria                                                                        | SLA                                                    |
| ----------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------ |
| **P1 — Critical** | Production down, data loss/corruption, security breach, all/most users affected | Respond 1hr, continuous work, updates every 1-2hr      |
| **P2 — High**     | Core workflow broken, many users affected, no workaround, time-sensitive        | Respond 4hr, same-day investigation, updates every 4hr |
| **P3 — Medium**   | Feature partially broken, workaround exists, single user/small team             | Respond 1 business day, resolution within 3 days       |
| **P4 — Low**      | Cosmetic issue, feature request, general question, documented solution          | Respond 2 business days, normal pace                   |

Bump priority up when: multiple customers report same issue, customer has exceeded SLA wait, customer escalates to executive, workaround stops working, or scope expands.

## Routing Rules

| Route to            | When                                                                               |
| ------------------- | ---------------------------------------------------------------------------------- |
| **Tier 1**          | How-to, known issues with documented solutions, billing inquiries, password resets |
| **Tier 2**          | Bugs requiring investigation, complex configuration, integration troubleshooting   |
| **Engineering**     | Confirmed bugs needing code fixes, infrastructure issues, performance degradation  |
| **Product**         | Feature requests with significant demand, design decisions, workflow gaps          |
| **Security**        | Data access concerns, vulnerability reports, compliance questions                  |
| **Billing/Finance** | Refund requests, contract disputes, complex billing adjustments                    |

## Duplicate Detection

Before routing, check for duplicates by symptom, customer, product area, and known issues. If a duplicate is found: link tickets, notify the customer, add new information to the existing ticket, and bump priority if the new report adds urgency.