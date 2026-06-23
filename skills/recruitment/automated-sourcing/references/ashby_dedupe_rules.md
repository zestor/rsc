# Ashby Dedupe Rules

## What "Ashby checked" must mean

The UI must never display a binary "Ashby checked: Yes" without indicating what was actually checked. The renderer expects:

- `ashby.check_status`: `checked` / `partial` / `unavailable`.
- `ashby.match_status`: `clear` / `possible_duplicate` / `excluded` / `unknown`.
- `ashby.match_confidence`: `high` / `medium` / `low` / `none`.
- `ashby.match_reason`: short human-readable description.

Example surfaces:

- `Ashby: clear (high) — No LinkedIn or name match in Ashby.`
- `Ashby: possible_duplicate (low) — Name match only; no LinkedIn URL.`
- `Ashby: excluded (high) — Already in pipeline (req-…)`. The req ID is preserved in the data payload but not surfaced into UI text.

## What to match on

In priority order:

1. Normalized LinkedIn URL.
2. Normalized profile URL.
3. Verified email.
4. Full name + current company.
5. Full name + recent company.
6. Known aliases.
7. Public profile evidence.

## Pre-send duplicate gate

Before adding a candidate to the static UI bundle as new, the workflow must:

- Re-check the SQLite store.
- Re-check the Ashby exclusions list.
- If `match_confidence` is `medium` or `high`, do not include the candidate in the published bundle. Store the dropped candidate in a debug table for review.

## Exclusion list display

The renderer normalizes the Ashby exclusion list with these rules:

- `candidate_name` displayed first.
- `reason` / `status` displayed second.
- `excluded_at` displayed as a human-readable date (no time component required).
- Raw internal IDs (req IDs, Ashby candidate IDs) are kept on the data payload but not surfaced into display text.
- Repeated entries with identical `(candidate_name, reason, status, excluded_at)` are deduped at render time.
