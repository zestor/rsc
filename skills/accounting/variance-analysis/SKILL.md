# Variance Analysis

Decomposition formulas, materiality thresholds, narrative structure, and waterfall methodology.

## Decomposition Formulas

### Price / Volume (revenue, COGS, any Price x Volume metric)

```
Volume Effect = (Actual Volume - Budget Volume) x Budget Price
Price Effect  = (Actual Price - Budget Price) x Actual Volume
Verification: Volume Effect + Price Effect = Total Variance
```

Three-way (separating mix):

```
Volume Effect = (Actual Vol - Budget Vol) x Budget Price x Budget Mix
Price Effect  = (Actual Price - Budget Price) x Budget Vol x Actual Mix
Mix Effect    = Budget Price x Budget Vol x (Actual Mix - Budget Mix)
```

### Headcount / Compensation

```
Headcount variance = (Actual HC - Budget HC) x Budget Avg Comp
Rate variance      = (Actual Avg Comp - Budget Avg Comp) x Budget HC
Mix variance       = Difference due to level/department mix shift
Timing variance    = Partial-period effect of hiring earlier/later than planned
Attrition impact   = Savings from unplanned departures (offset by backfill costs)
```

### OpEx Spend Categories

Decompose into: headcount-driven (salaries, benefits, recruiting), volume-driven (hosting, transaction fees, commissions), discretionary (travel, events, professional services), contractual/fixed (rent, insurance, licenses), one-time/non-recurring (severance, legal, write-offs), and timing/phasing.

## Materiality Thresholds

| Comparison             | Dollar Threshold                 | % Threshold | Trigger         |
| ---------------------- | -------------------------------- | ----------- | --------------- |
| Actual vs Budget       | Org-specific (0.5-1% of revenue) | 10%         | Either exceeded |
| Actual vs Prior Period | Org-specific                     | 15%         | Either exceeded |
| Actual vs Forecast     | Org-specific                     | 5%          | Either exceeded |
| Sequential (MoM)       | Org-specific                     | 20%         | Either exceeded |

Scale dollar thresholds by line item size: >$10M lines use $500K/5%, $1-10M use $100K/10%, <$1M use $50K/15%.

Prioritize investigation by: largest absolute dollar variance, largest percentage variance, unexpected direction, new variances (previously on track), and cumulative/trending variances.

## Variance Narrative Structure

```
[Line Item]: [Favorable/Unfavorable] $[amount] ([%]%) vs [basis] for [period]
Driver: [Primary driver]
[2-3 sentences: business reason, quantified contributing factors]
Outlook: [One-time / Continuing / Improving / Deteriorating]
Action: [None / Monitor / Investigate / Update forecast]
```

Anti-patterns: circular explanations ("revenue was higher due to higher revenue"), unquantified "timing" without specifying what shifted and when it normalizes, "one-time" without identifying the item, "various small items" for a material variance.

## Waterfall / Bridge Format

```
Starting value (Budget/Prior)         $X,XXXK
  [+] Driver A                         +$XXXK
  [+] Driver B                         +$XXXK
  [-] Driver C                          -$XXXK
  [-] Driver D                          -$XXXK
Ending value (Actual/Current)         $X,XXXK
Net Variance: +/-$XXXK (+/-X.X%)
```

Keep to 5-8 drivers; aggregate smaller items into "Other." Verify start + drivers = end.

## Forecast Accuracy

```
Forecast Accuracy = 1 - |Actual - Forecast| / |Actual|
MAPE = Average of |Actual - Forecast| / |Actual| across periods
```

Trending signals: consistently favorable = budget too conservative, consistently unfavorable = aggressive targets or execution issues, growing unfavorable = deteriorating performance, volatile = poor forecasting methodology.

## Gotchas

- **Mix effect is the most commonly omitted driver** -- when product or segment mix shifts, blended margins change even if unit prices and volumes are flat; always decompose mix separately.
- **Percentage variance on small bases is misleading** -- a $5K line item going to $15K is 200% variance but immaterial; always pair percentage with absolute dollar.
- **"Timing" requires a payback period** -- if spend shifted from Q1 to Q2, Q2 must show the corresponding unfavorable variance; if it doesn't, it wasn't timing.
- **Budget-vs-actual and forecast-vs-actual tell different stories** -- budget variance measures plan execution; forecast variance measures prediction accuracy. Conflating them produces useless narratives.
- **Offsetting variances hide risk** -- revenue +$500K and COGS +$500K nets to zero margin variance, but each deserves separate investigation because the drivers may be unrelated.