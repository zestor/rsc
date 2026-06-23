# Competitive Intelligence

Research competitors and generate an **interactive HTML battlecard** — a self-contained artifact with clickable competitor tabs and a comparison matrix.

## Execution Flow

1. **Gather seller context** — Ask what company the user works for, what they sell, and who their competitors are (up to 5). If returning user, confirm existing context.
2. **Research your company** — Web search for product, pricing, news, releases, and existing comparisons (last 90 days).
3. **Research each competitor** — For each: product features, pricing, news, releases, reviews (G2/Capterra/TrustRadius), positioning, customers, and hiring signals.
4. **Pull connected sources** (if available) — CRM for win/loss data, docs for existing battlecards, chat for field intel, transcripts for competitor mentions.
5. **Build HTML artifact** — Structure data per competitor, build comparison matrix, generate battlecards with talk tracks and landmine questions. Use the template in `references/battlecard-template.html` as the base. Save as `[Company]-battlecard-[date].html`.

## Connector Enrichment

| Connector       | What It Adds                                                        |
| --------------- | ------------------------------------------------------------------- |
| **CRM**         | Win/loss history, deal-level competitor tracking, win rate patterns |
| **Docs**        | Existing battlecards, product comparisons, competitive playbooks    |
| **Chat**        | Field intel from colleagues, competitor mentions (last 90 days)     |
| **Transcripts** | Competitor mentions in calls, objections, customer quotes           |

No connectors? Web research alone works — product pages, pricing, blogs, release notes, reviews, job postings.

## Per-Competitor Data Model

See `references/competitor-schema.yaml` for the full data structure to populate for each competitor: profile, recent releases, win/lose areas, pricing intel, talk tracks, objections, and landmine questions.

## Gotchas

- **Don't badmouth competitors** — Ask landmine questions that expose weaknesses naturally. Never trash-talk.
- **Be honest about where you lose** — Credibility comes from acknowledging competitor strengths. Reps who only say "we win everywhere" lose trust.
- **Reviews lag reality** — G2/Capterra reviews are 6-12 months stale. Cross-reference with recent release notes and job postings for current direction.
- **Pricing pages lie** — Published pricing often omits enterprise discounts, implementation fees, and per-seat minimums. Flag anything unverifiable as "reported" not "confirmed."
- **Job postings reveal strategy** — If a competitor is hiring 20 ML engineers, they're building AI features whether they've announced them or not.

## Related Skills

- `sales/account-research` — Research a specific prospect before reaching out
- `sales/call-prep` — Prep for a call where competitor is involved
- `sales/create-an-asset` — Build a custom comparison page for a specific deal