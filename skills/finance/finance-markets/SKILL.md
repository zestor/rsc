# Finance Markets

## Bootstrap

Run two calls (parallelizable):

- `memory_search` with `query="finance provider preference"` — look up any saved cross-session preference.
- `list_external_tools` with `queries=["finance_", "factset", "daloopa", "morningstar", "carbonarc"]` — list available BYOL providers.

The list result includes a `load_skill(name="...")` hint for any returned source_id that has a registered connector skill. **If a connector skill is hinted, load it before calling that provider's tools** — it carries provider-specific tool patterns and gotchas that the bare schema does not. If memory returned a preferred provider that is among the hinted source_ids, prefer that one.

If no connector skill is hinted and no provider preference is saved, **silently** use Perplexity's built-in `finance_*` tools — just answer the question. Do **not** narrate the choice, do **not** mention which providers are connected or disconnected, and do **not** supplement with any open-web retrieval (search tools, shell commands, URL fetches, scraping). Read `builtin-tools.md` for the full catalog and execution patterns.

The built-ins are also fine for explicit data gaps that a connected provider does not cover, but they are **not a substitute** for connecting (or re-connecting, if status is `OUTDATED`) to a *preferred* provider — when memory or the user has flagged a provider as preferred and it is unavailable, surface the connect/reconnect step instead of silently falling back to built-ins.

If the user expresses a cross-session provider preference (e.g. "always use Factset for finance"), call `memory_update` to persist it.

## Sibling reference files (read on demand)

- `builtin-tools.md` — the built-in `finance_*` tool catalog, parameters, examples, and full citation mechanic. Required reading before calling any built-in finance tool.
- `analysis.md` — DataFrame / calculation patterns (ratios, comparable analysis, DCF, statistical analysis).
- `reporting.md` — formatting, tables, chart recommendations, and report templates.
- `websites.md` — building dashboards, reports with embedded charts, and any web output backed by finance data.

## Citations (mandatory for built-in `finance_*` tools)

**Every numeric value pulled from a built-in `finance_*` tool — raw lookups (revenue, EPS, market cap, balance-sheet line items, estimates) AND derived values (margins, growth rates, ratios) — must:**

1. Pass through `cite()` from `skills/finance/finance-markets/citations.py`, AND
2. Appear in your response text as `[value](claim:N)` claim links.

A response with finance numbers but no claim markers is a failure.

This rule applies **even when you already know the answer**: every finance number you state must come from an actual `finance_*` tool call, pass through `cite()`, and appear as `[value](claim:N)` in your response. Short answers, follow-ups, and "obvious" lookups are not exempt — there is no shortcut. **Never type literal `[value](claim:N)` markers without actually running `cite()`** — fabricated markers look right but carry no provenance and will not render. If you produced markers without a `cite()` call, you have failed the citation requirement.

Citations apply only to built-in `finance_*` tools that return CSV files with citation provenance. They do **not** apply to BYOL connector tools or to web-search results — never call `cite()` with web or BYOL data.

The full mechanic — `# __cite_setup__` blocks, source vs. derived `cite()` signatures, the `[value](claim:N)` link grammar, `derived_from` matching, and the do-not-narrate-plumbing rule — lives in `builtin-tools.md`. **After loading this skill, read `skills/finance/finance-markets/builtin-tools.md` with the read tool before any finance_* call.** Its Citations section is the source of truth and you must follow it line for line.

**Sanity check before responding:** every claim ID you reference must come from stdout of any `cite()` script you ran in this session. If you have not run a `cite()` flow at all, your response must contain no `(claim:N)` markers — go run it first.

## Scope

- **Do NOT** use these tools for the user's own brokerage portfolio, balances, or transactions — that is `personal-finance`.
- **Do NOT** fall back to open-web retrieval (search tools, shell commands, URL fetches, scraping) for price or fundamental data — finance providers return structured, point-in-time accurate data; the open web does not.