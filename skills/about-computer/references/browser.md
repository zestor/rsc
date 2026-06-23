# Browser Automation

When programmatic search isn't enough — login-gated sites, interactive forms, dynamic JavaScript pages — Computer launches a full cloud browser.

## What it can do

- Navigate to any URL, click elements, fill forms, and extract structured data.
- Handle multi-step web flows (login → navigate → extract → download).
- Handle authenticated sessions when the user provides credentials.
- Take high-fidelity screenshots of any webpage.
- Run batch browser tasks across dozens of URLs in parallel.
- Use the user's own browser session on Desktop Comet, preserving login state and cookies for authenticated sites.

## When to use browser vs. search

| Use search when...                                | Use browser when...                               |
| ------------------------------------------------- | ------------------------------------------------- |
| Information is on public, openly accessible pages | Site requires login or authentication             |
| You need facts, prices, news                      | You need to interact with a form or UI            |
| Speed matters (search is faster)                  | Content is behind JavaScript rendering            |
| You need results from multiple sources            | You need to take actions (submit, purchase, post) |

## Batch processing

For tasks that require visiting many URLs — extracting pricing from 50 competitor sites, collecting product details, or checking status pages — Computer can run browser tasks in parallel across all of them. Results are collected into structured output (typically CSV).

## Example use cases

- Extract pricing tiers from competitor websites that don't have public APIs.
- Fill out web forms across multiple sites.
- Take screenshots of web pages for a visual audit.
- Collect job listings from career pages (search engines return stale job results).
- Navigate authenticated dashboards to pull metrics or reports.
