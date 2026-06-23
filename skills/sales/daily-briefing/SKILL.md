# Daily Sales Briefing

Produce a prioritized view of what matters most today.

## Execution Flow

1. Pull today's meetings (calendar or user input)
2. Query open pipeline (CRM or user input)
3. Check priority emails (email connector or user input)
4. Rank by urgency and generate briefing

## Connector Enrichment

| Connector      | What It Adds                                                  |
| -------------- | ------------------------------------------------------------- |
| **Calendar**   | Today's meetings with attendees, times, and context           |
| **CRM**        | Open pipeline, deals closing soon, overdue tasks, stale deals |
| **Email**      | Unread from opportunity contacts, emails awaiting replies     |
| **Enrichment** | Overnight signals: funding, hiring, news on your accounts     |

## Priority Ranking

1. Deal closing today/tomorrow not yet won
2. Meeting today with high-value opportunity
3. Unread email from a decision-maker
4. Deal closing this week
5. Stale deal (7+ days no activity)
6. Tasks due this week

## Briefing Structure

1. **#1 Priority** -- the single most important thing to do today, with why
2. **Today's Numbers** -- open pipeline, closing this month, meetings, action items
3. **Today's Meetings** -- per-meeting: time, company, attendees, context, pre-meeting action
4. **Pipeline Alerts** -- deals needing attention and deals closing this week
5. **Suggested Actions** -- top 3 actions with urgency rationale

## Variants

- **Quick brief** ("tldr my day"): #1 priority, meeting list, top alert, single action
- **End of day** ("wrap up my day"): completed meetings with outcomes, pipeline changes, tomorrow's focus, open loops

## Gotchas

- **Calendar noise** -- filter to external meetings; internal standups and 1:1s are not sales-relevant.
- **Pipeline amounts lie** -- deals at "negotiation" with no recent activity are not real pipeline; flag them.
- **Recency bias** -- a loud email from a small deal can distract from a quiet large deal closing Friday; rank by value, not noise.
- **Meeting prep is a separate skill** -- the briefing should surface that a meeting exists and needs prep, then point to `call-prep`.
- **Stale deal threshold depends on sales cycle** -- 7 days is a heuristic; enterprise deals with 90-day cycles need different thresholds.