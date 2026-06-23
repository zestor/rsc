# Finance Digest Email

Use `email_args.template="finance_digest"` for emails primarily about the user's holdings, net worth, or portfolio movement. The template renders an `overview_items` strip of metric cards at the top and a stack of titled `sections` below.

The shape of `overview_items` and `sections` is enforced by the tool schema (each is a list of `{key, value}` items, 1–4 entries). This skill covers the *content* discipline that the schema can't express.

## Number formatting

Apply consistently across `overview_items` values and any numbers that appear inside `sections`:

- **Always include thousands separators** in dollar values: `$125,430.12`.
- **Always include an explicit `+` or `-` sign** on day-change figures.
- **Decimal precision:** 2 dp for dollar values, 1–2 dp for percentages. Pick one percent precision and stay consistent within a single email.

## Scope: net worth vs portfolio-only

Net-worth and portfolio overview values must reference the same scope across the strip. If you want both, use two cards (`Net Worth` + `Portfolio`) and report the day change against whichever you led with.

## Section content rules

Each section's `value` is markdown. It runs through the markdown → HTML pipeline (sanitized via bleach), so `**bold**`, `[links](https://…)`, and inline `code` all render.

- **Link tickers to their Perplexity Finance page** — `[AAPL](https://www.perplexity.ai/finance/AAPL)`. Same `/finance/<TICKER>` pattern for stocks, ETFs, and mutual funds (`/finance/FXAIX`).
- **Inline links to news sources that drove movement:** `Apple's earnings beat ([WSJ](https://...))`.
- **A single `**bold**` phrase** to emphasize the headline takeaway, if any.
- **Keep prose to 2–4 sentences per section.** Sections are titled boxes.
- **Show per-ticker data as a short markdown bullet list** capped at ~5 items when you need prices, watchlist values, or holdings.

### Top Movers section discipline

If you include a `Top Movers` section, the `value` should be a markdown bullet list:

- **Cap at 3–5 items.** More is a wall.
- **Only include movers with ≥0.5% absolute move** (or whatever threshold genuinely separates signal from noise that day). If nothing crossed the threshold, **omit the `Top Movers` section entirely**.
- **Mix winners and losers** when both exist — a list of all-up or all-down movers misrepresents the day.
- **Link each ticker** at `https://www.perplexity.ai/finance/<TICKER>` (uppercase). The link becomes the bold anchor:
  ```
  - [**PLTR**](https://www.perplexity.ai/finance/PLTR) +3.6%
  - [**ONON**](https://www.perplexity.ai/finance/ONON) -3.0%
  ```

## Title

The title doubles as the email subject (unless `email_args.subject` overrides) and the in-app notification headline. The email's preview headline ("Your daily portfolio snapshot") is **fixed by the template** — agent does not control it.

Make the title scannable at a glance — anchor on the headline metric, the date, or the most notable mover.

- ✅ Good: `"Portfolio +0.99% today"`, `"Your finance snapshot — Apr 30"`, `"NVDA +12% led your portfolio today"`
- ❌ Bad: `"Update"`, `"Your digest"`, `"Daily summary"`, `"Your Daily Portfolio Digest"` (echoes the cron description, looks like spam), `"Here is the summary of your personal finances you requested"` (echoes the prompt, no signal)

**Quiet days still get a digest, but the title should reflect that honestly.** If nothing crossed a meaningful threshold, say it plainly: `"Markets quiet — portfolio +0.1%"`, `"Flat day — no major movers"`. The user expects the recurring email; an honest quiet-day title beats a spammy one.

Use percentages and qualitative descriptors in the title; put absolute figures (`$125,430.12`, `+$1,234.56`) in `overview_items`. If you need a dollar amount in the in-app notification specifically, override `email_args.subject` with a sanitized email-safe version.

## Gotchas

- **Don't omit thousands separators.** Dollar values should read like `$125,430.12`, never `$125430.12`.
- **Don't leave day-change values unsigned.** A bare `0.99%` next to "Day Change" reads ambiguously (negative? positive? rounded from zero?).
- **Don't mix scopes across the overview strip.** Total net worth and portfolio-only daily change refer to different scopes; keep net-worth and portfolio overview values aligned or split them into separate cards.
- **Don't repeat the heading inside the section value.** The template already renders `key` as the section heading; starting `value` with `## Market Summary` creates a duplicate header.
- **Don't restate overview metrics.** Net worth and day change are already in the cards above; referring back to them as commentary is fine ("modestly green day"), enumerating them again is not.
- **Don't dump multi-paragraph essays into sections.** Sections are titled boxes; keep the prose to 2–4 sentences per section.
- **Don't overload sections with ticker data.** The template doesn't render markdown tables — they come through as raw text in the email. Use a short markdown bullet list for per-ticker data instead, and cap it at ~5 items.
- **Don't pad `Top Movers` with sub-noise positions.** If nothing crossed the threshold that genuinely separates signal from noise that day, omit the `Top Movers` section entirely.
- **Don't use 🟢 / 🔴 (or other) emoji prefixes in `Top Movers`.** The signed percentage already encodes direction, emoji renders inconsistently across email clients (Outlook on Windows often shows monochrome boxes), and adds an accessibility tax for color-blind readers.
- **Don't fake-anchor quiet-day titles.** If nothing crossed a meaningful threshold, don't anchor on a tiny mover or fall back to a generic "Daily summary"; an honest quiet-day title beats a spammy one.
- **Keep concrete dollar amounts and account balances out of the title.** The title doubles as the email subject, which is visible on lock-screen previews and can trigger spam filters.

## Example

```
send_notification(
  title="Portfolio +0.66% today — AAPL led tech rally",
  body="S&P 500 closed at a record on Apple's earnings beat.",
  channels=["email"],
  email_args={
    "template": "finance_digest",
    "overview_items": [
      {"key": "Net Worth", "value": "$128,430.22"},
      {"key": "Portfolio", "value": "$115,629.18"},
      {"key": "Day Change", "value": "+$842.13 (+0.66%)"},
    ],
    "sections": [
      {
        "key": "Market Summary",
        "value": (
          "S&P 500 closed at a record (+0.3%) on Apple's earnings beat — "
          "[AAPL](https://www.perplexity.ai/finance/AAPL) +3.2% drove tech "
          "leadership across the board."
        ),
      },
      {
        "key": "Top Movers",
        "value": (
          "- [**PLTR**](https://www.perplexity.ai/finance/PLTR) +3.6%\n"
          "- [**AAPL**](https://www.perplexity.ai/finance/AAPL) +3.2%\n"
          "- [**TSLA**](https://www.perplexity.ai/finance/TSLA) +2.4%\n"
          "- [**ONON**](https://www.perplexity.ai/finance/ONON) -3.0%"
        ),
      },
      {
        "key": "Spending",
        "value": (
          "Card spend $128.40 today across 3 transactions — biggest was "
          "$74.10 at Whole Foods. On pace for ~$3,800 this month, in line "
          "with your trailing 30-day average."
        ),
      },
    ],
  },
)
```