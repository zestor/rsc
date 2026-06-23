# Talent pool rendering

Deterministic preview renderer for a Talent Pool dashboard. Takes a `TalentPoolBundle` JSON in, writes a self-contained static HTML preview out. No backend, no SQLite, no API client. The preview is a screenshot-quality visualization — not a production review surface.

## Pipeline

```text
   TalentPoolBundle JSON (matches schemas.py)
                  │
                  ▼
   formatting.py (deterministic, stdlib-only)
                  │
                  ▼
   templates/talent_pool_app.{html,css,js}
   + shared/ui/tokens.css (linked from output)
                  │
                  ▼
   static HTML bundle in --output dir
```

## Rules

- **Preview only.** The output is a self-contained static bundle. It must not be treated as a production review surface. There is no API client, no backend, no SQLite, no add-candidate flow, no scheduling, no alerts.
- **Schema is the contract.** `schemas.py` defines `TalentPoolBundle` with `Candidate`, `Signal`, `Source`, `CompanySnapshot`, `Methodology`, `MethodologySignal`, `Run`, `TierThresholds`, and `WorkflowSettings`. The renderer reads only schema-typed input.
- **Renderer is deterministic.** `formatting.py` is stdlib-only Python and pure: same `TalentPoolBundle` input → byte-identical output. Tier assignment, ranking, and label normalization happen in code, not in prompts.
- **Tier assignment is simple.** Preserve a candidate's provided tier; otherwise bucket `final_score` using `tier_thresholds`.
- **Safe link rendering.** Candidate profile URLs render as text-only `<a>` elements with `target="_blank" rel="noopener noreferrer"` and `http`/`https` scheme validation. Non-http(s) URLs are dropped at render time. Only the link text is clickable; there is no surrounding icon hit area.
- **No shipped sample bundle.** This skill does not ship a fixture bundle. Any preview/test input lives outside the skill directory; if you need synthetic data, generate it in a scratch location (e.g. `/tmp/`). Do not commit real candidate PII, fixtures, or generated bundles inside the skill directory. Runtime user-provided candidate data may be rendered from scratch paths or workflow outputs.
- **No LLM string-insertion into HTML.** Add new UI fields to `schemas.py` first, then render through `formatting.py`.
- **Reuse shared tokens.** The output bundle links `tokens.css` from `recruitment/shared/ui/`. Keep global color, typography, radius, spacing, and base theme tokens in the shared file. Keep Talent Pool-specific component and tier styling in `templates/talent_pool_app.css`.
- **Workflow / status / seed information renders at the bottom of the page.** The leaderboard is the primary grid. Workflow data does not push the main grid right. Top navigation can include section jump links such as Candidates, Methodology, and Workflow data; the workflow link anchors-scrolls to the bottom section.
- **Deduplicate headline vs current position.** If the detail headline is a token-level subset of the current position, render only the current position.

### Render the preview

The renderer takes an existing `TalentPoolBundle` JSON file as input. No sample bundle is shipped inside this skill directory — keep any preview/test input outside the skill (e.g. `/tmp/` or another scratch location) and do not commit it.

```bash
python3 pplx/python/apps/asi/skills/recruitment/talent-pool-rendering/formatting.py \
    --input /path/to/your/talent_pool_bundle.json \
    --output /tmp/talent-pool-preview/
```

The output directory contains `index.html`, `app.css`, `tokens.css`, `app.js`, and the normalized bundle JSON. Open `index.html` in a browser.

## References

- `references/talent_pool_preview_contract.md` — read when changing the rendered layout, leaderboard, detail pane, or bottom workflow section. Spells out the exact preview contract.

## What's deferred

- [ ] Backend persistence (SQLite, API, add-candidate flow). Out of scope for this skill.
- [ ] Tier refresh scheduling. Out of scope for this skill.
- [ ] Tier-change alerts. Out of scope for this skill.
- [ ] Reviewer write-back (Yes / Maybe / No). Out of scope for this skill.