# Talent pool preview contract

**Read when** changing layout, leaderboard, detail rendering, or the bottom workflow section of the preview.

## Layout

- Single content column, max-width capped by `--content-max`.
- Sticky top bar with role label, subtitle, theme toggle, and section jump links. Current top links are `Candidates`, `Methodology`, and `Workflow data`; the workflow link smooth-scrolls to `#workflow-data` and does not break hash routing.
- Tier summary band (Hot / Warm / Watch / Cold) sits directly under the top bar with one card per tier.
- Leaderboard occupies the primary area and lists every candidate, sorted by tier then score then name.
- Candidate details open in a right-side drawer. The drawer contains profile context plus the full signal breakdown.
- Companies in scope and methodology render below the leaderboard before workflow data when present.
- Workflow data (settings, tier thresholds, run history) renders in a section at the bottom of the page, not in a sidebar. It must not push the leaderboard right.

## Candidate row

- Rank, score dial, name, tier pill, subline of `current_title · current_company · location`, optional headline (italic, muted) only if it is not a token-level subset of the position string, and an arrow affordance.
- The row button opens the candidate side drawer. Separate text links below the row content expose `LinkedIn` and `Details`.
- Profile link is text-only "LinkedIn" with `target=_blank rel=noopener noreferrer`. Only the text is clickable; there is no surrounding icon hit area.

## Candidate drawer

- Opens from the right without leaving the leaderboard.
- Header shows score dial, name, tier, current title, current company, location, and LinkedIn link when available.
- Signal cards render every `Candidate.signals` entry with `score/10`, weight, weighted contribution, progress bar, rationale, and safe source links.

## Companies and methodology

- `companies` render as cards with name, stability label, summary, and safe source links.
- `methodology` renders the formula, total weight, tier cutoffs, and a signal-weight table.

## Safe link rendering

- Profile URLs are dropped at render time unless the scheme is `http` or `https` and a host is present. Non-http(s) URLs do not render.

## Determinism

- Same `TalentPoolBundle` JSON in → byte-identical files out.
- Sort order: tier order (hot → cold), then descending `final_score`, then `full_name` ascending.
- Tier is recomputed from `final_score` and `tier_thresholds` if not already present.
