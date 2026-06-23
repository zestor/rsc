# Metrics Tracking

## Product Metrics Hierarchy

### North Star Metric

The single metric capturing core value delivered. Must be: value-aligned (moves when users get value), leading (predicts long-term business success), actionable (team can influence it), understandable (everyone grasps it).

### L1 Metrics (Health Indicators)

5-7 metrics covering the user lifecycle:

- **Acquisition**: New signups, signup conversion rate, channel mix, CAC
- **Activation**: Activation rate (% completing the key action predicting retention), time to activate, setup completion
- **Engagement**: DAU/WAU/MAU, DAU/MAU ratio (stickiness), core action frequency, feature adoption
- **Retention**: D1/D7/D30 retention, cohort retention curves, churn rate, resurrection rate
- **Monetization**: Free-to-paid conversion, MRR/ARR, ARPU, expansion revenue, net revenue retention
- **Satisfaction**: NPS, CSAT, support ticket volume, app store ratings

### L2 Metrics (Diagnostic)

Used to investigate L1 changes: funnel step conversion, feature-level usage, segment breakdowns (plan, company size, geography, role), performance metrics (latency, error rate).

## Key Metric Definitions

**DAU/MAU ratio (stickiness)**: Above 0.5 = daily habit. Below 0.2 = infrequent usage. Trend matters more than absolute number. Always segment by user type.

**Retention**: Plot cohort curves. Initial drop-off = activation problem. Steady decline = engagement problem. Flattening = stable retained base. Compare cohorts over time to measure product improvement.

**Activation**: The action that predicts long-term retention. Find by comparing retained vs. churned user behaviors. Should be achievable in first session or first few days.

## OKR Framework

**Objectives**: Qualitative, aspirational, time-bound (quarterly/annually). 2-3 per period.

**Key Results**: Quantitative, specific, outcome-based. 2-4 per Objective. 70% completion is the target for stretch OKRs.

Setting targets requires: baseline (current value), benchmark (comparable products), trajectory (current trend), and effort level (investment behind it). Set a "commit" (high confidence) and a "stretch" (ambitious).

## Dashboard Design Principles

1. Start with the decision the dashboard supports, not the data available
2. North Star at top, L1 metrics next, L2 on drill-down
3. Every number needs context: current value, comparison period, target, trend direction
4. 5-10 metrics max. Everything else in a detailed report
5. Every metric must be something the team can influence

Anti-patterns: vanity metrics (total signups ever), no comparison context, stale dashboards, measuring team output instead of user outcomes, one dashboard for all audiences.

## Gotchas

- **Averages lie** — A 3.5 average could mean everyone is lukewarm or half love it and half hate it. Always look at distributions.
- **Defining "active" wrong changes everything** — DAU based on login vs. core action tells completely different stories. Define carefully and consistently.
- **Vanity metrics feel good but mislead** — "Total users" always goes up. Track rates and ratios that can go down.
- **Too many OKRs dilute focus** — More than 3 objectives with 4 KRs each and nobody remembers them. Fewer, more ambitious targets win.
- **Alerting without owners is noise** — Every alert needs an owner who responds when it fires. Unowned alerts train people to ignore all alerts.