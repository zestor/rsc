# Investment Research

Ground every conclusion in data from finance tools. Do not speculate when a tool call can provide the answer.

| Signal                                                 | Mode        |
| ------------------------------------------------------ | ----------- |
| Screening, filtering, ranking, "find stocks that..."   | **Find**    |
| Specific conviction, "should I buy X?", thesis testing | **Think**   |
| Named investor or investing style/philosophy           | **Imitate** |
| Portfolio holdings, diversification, risk, rebalancing | **Analyze** |

## Find

Filter a universe of stocks by user criteria and surface the best candidates. Use `finance_etf_holdings` to seed a sector universe, apply filters in Python, then enrich the top 5-10 via `finance_quotes`, `finance_company_financials`, and `finance_earnings`. Use parallel subagents when enriching more than 3 tickers.

## Think

Pressure-test a specific investment thesis. Restate the thesis as: asset, belief, time horizon, expected outcome. Gather financials (5-year trends, ratio analysis), earnings transcripts (guidance vs actuals, tone shifts), price context, and qualitative signals (news, competitive dynamics). Present bull/bear cases for each core assumption with supporting data. Conclude with a thesis strength rating, key evidence, key risks, and upside/base/downside scenario table.

## Imitate

Evaluate a stock through a famous investor's philosophy. Read the matching profile from [investor-profiles.md](investor-profiles.md) and score each quantitative criterion as Pass / Borderline / Fail. Assess qualitative criteria from transcripts and news. Present as a scorecard with thresholds, actuals, and verdicts.

## Analyze

Assess a portfolio's composition and risk. Check `list_external_tools` for a connected brokerage (Plaid `portfolio_holdings`) before asking the user to list holdings manually. Fall back to `memory_search` for a previously stored portfolio. Compute:

- Concentration risk (position sizes, HHI)
- Correlation matrix from daily returns
- Portfolio beta, annualized volatility, Sharpe ratio vs SPY
- Weighted average valuation (P/E, P/S, P/B) vs market averages

Flag: single position >20%, pair correlation >0.8, sector weight >40%, weighted P/E >2x or <0.5x market average.

## Backtesting

Temporal integrity is a hard constraint for any historical evaluation.

- Insert a censor gap (default: 1 trading day) between data cutoff and evaluation window. Financials have reporting lags.
- Compute returns using price data strictly after the censored decision point.
- Never use future prices, earnings, or revisions to construct a past portfolio.
- If a censor window cannot be verified, stop and tell the user. A leaky backtest is worse than none.

## Gotchas

- **Survivorship bias in screens** — Stock screeners only return currently listed companies. Screens over historical periods silently exclude delisted/bankrupt stocks, inflating apparent returns.
- **Stale financials near earnings** — `finance_company_financials` returns the most recent filed data. In the weeks before an earnings release, trailing metrics can be 3+ months old and materially misleading for fast-growing or deteriorating companies.
- **ETF holdings lag** — `finance_etf_holdings` data can be 30-90 days stale. Constituent changes (additions, removals, rebalances) may not be reflected.
- **Adjusted vs unadjusted prices** — `finance_ohlcv_histories` returns split/dividend-adjusted prices by default. Raw price comparisons to historical targets or news-quoted prices will be wrong.
- **Correlation regimes shift** — Asset correlations computed from calm-market data understate drawdown risk. Correlations spike toward 1.0 during market stress, exactly when diversification is needed most.

End every investment research response with: _This is research and analysis only, not personalized financial advice. Consult a qualified financial advisor before making investment decisions._