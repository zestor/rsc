# Performance Analytics

## Key Metrics by Channel

### Email

| Metric           | Definition                   | Benchmark |
| ---------------- | ---------------------------- | --------- |
| Open rate        | Unique opens / delivered     | 15-30%    |
| CTR              | Unique clicks / delivered    | 2-5%      |
| CTOR             | Unique clicks / unique opens | 10-20%    |
| Unsubscribe rate | Unsubscribes / delivered     | <0.5%     |
| Conversion rate  | Conversions / delivered      | 1-5%      |

### Paid Advertising

| Metric                 | Definition                                                     |
| ---------------------- | -------------------------------------------------------------- |
| CTR                    | Clicks / impressions                                           |
| CPC                    | Spend / clicks                                                 |
| CPA                    | Spend / conversions                                            |
| ROAS                   | Revenue / ad spend                                             |
| Quality Score (search) | Google's ad-keyword-landing page relevance (1-10)              |
| Frequency              | Average times a user sees the ad — watch for fatigue above 3-4 |

### SEO / Organic

| Metric                  | What It Tells You                         |
| ----------------------- | ----------------------------------------- |
| Organic sessions        | SEO effectiveness and content reach       |
| Keyword rankings        | Search visibility for target terms        |
| Organic CTR             | Title and meta description effectiveness  |
| Domain authority        | Overall site strength (third-party score) |
| Organic conversion rate | Content quality and intent alignment      |

### Pipeline

| Metric                       | Definition                                   |
| ---------------------------- | -------------------------------------------- |
| MQL to SQL rate              | SQLs / MQLs — marketing-sales alignment      |
| CAC                          | Total marketing + sales cost / new customers |
| CAC payback period           | Months to recover CAC from revenue           |
| Marketing-sourced revenue    | Revenue from marketing-originated deals      |
| Marketing-influenced revenue | Revenue from deals marketing touched         |

## Attribution Models

| Model                     | Credit Distribution             | Best For                                |
| ------------------------- | ------------------------------- | --------------------------------------- |
| Last touch                | 100% to last interaction        | Understanding final conversion triggers |
| First touch               | 100% to first interaction       | Top-of-funnel effectiveness             |
| Linear                    | Equal across all touchpoints    | Fair channel representation             |
| Time decay                | More to recent touchpoints      | Balanced view favoring recency          |
| Position-based (U-shaped) | 40% first, 40% last, 20% middle | Most B2B companies as a starting point  |
| Data-driven               | Algorithmic based on patterns   | High-volume conversion environments     |

Start with last-touch if you have no model. Compare first-touch and last-touch to see which channels drive awareness vs. conversion. No model is perfect — use directionally, not as absolute truth.

## Optimization Framework

### Diagnose by Funnel Stage

| Stage         | Problem Signal                | Levers                                  |
| ------------- | ----------------------------- | --------------------------------------- |
| Awareness     | Low impressions/reach         | Budget, targeting, channel mix          |
| Interest      | Low CTR/engagement            | Creative, headlines, audience targeting |
| Consideration | High bounce, low time on page | Landing page content, page speed, UX    |
| Conversion    | Low conversion rate           | Offer, CTA, form length, trust signals  |
| Retention     | High churn                    | Onboarding, nurture, product experience |

### Prioritization

Rank on Impact x Effort: do high-impact/low-effort first, deprioritize low-impact/high-effort.

### Testing Minimums

- One variable at a time, success metric defined before launch
- Calculate required sample size before starting — do not end tests early
- Run for at least one full business cycle (typically one week for B2B)

## Gotchas

- **Open rates are unreliable since Apple MPP** — Apple Mail Privacy Protection pre-fetches emails, inflating open rates. Use CTOR or click-based metrics as your primary engagement signal.
- **ROAS without accounting for margins is misleading** — a 3x ROAS on a 20% margin product means you are losing money. Always factor in COGS and margin when evaluating ad spend efficiency.
- **Awareness channels always look bad in last-touch attribution** — display, social, and PR will never "win" on last-touch. If you only use last-touch, you will systematically defund your top-of-funnel.
- **Self-reported attribution is directional, not quantitative** — "how did you hear about us?" answers are biased toward memorable touchpoints (podcasts, events) and miss drip-exposure channels (display, social). Use it for qualitative color, not budget allocation.
- **Dashboards without decision cadence are decoration** — real-time dashboards for metrics reviewed monthly waste engineering effort. Match update frequency to decision frequency.