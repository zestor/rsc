# Candidate Sourcing Workflow

End-to-end procedure for the Automated Sourcing workflow that consumes this skill.

## Dependency on `search/recipes/people-research.md`

The composition rule — "reuse the `search` skill's people-research recipe, don't fork it" — is owned by `pplx/python/apps/asi/skills/recruitment/automated-sourcing/SKILL.md`. This doc consumes that rule; it does not redefine it. If the composition policy ever changes (e.g. a sub-recipe is hoisted into automated-sourcing, or a different search skill replaces `search`), update `SKILL.md` first and let this workflow doc track.

Practical implication for the pipeline below: the procedure for a sourcing pass — query variation axes, parallel-search shape, filter-vs-query rules, web-search fallbacks, snippet enrichment, optional dossier extraction — is in `pplx/python/apps/asi/skills/search/recipes/people-research.md`. Steps 1-4 below are pointers into that recipe, not re-implementations.

## Inputs

- Role brief (role label, must-have evidence, recent-domain window).
- Existing SQLite workflow database for this role (prior runs, prior candidates, prior feedback, Ashby exclusions, workflow settings).
- Hired seed profiles (synthetic or opt-in) for positive signal.

## Steps

1. **Plan the search** *(people-research recipe)* — write 3-5+ varied queries across the variation axes called out in `pplx/python/apps/asi/skills/search/recipes/people-research.md` (role-title forms, company-name forms, industry terms, scope slicing).
2. **Search candidates** *(people-research recipe)* — run the variants in parallel using the search skill's parallel-search primitives (see `pplx/python/apps/asi/skills/search/python/`) over `pplx_sdk.search.people` and deduplicate by URL. Use the search skill's resumable-run patterns if the pool exceeds the `bash()` 300s window.
3. **Enrich profiles** *(people-research recipe)* — call `pplx_sdk.content.fetch_many` in chunks over the deduplicated URLs to materialize profile fields the people index doesn't expose.
4. **Filter for fit** *(people-research recipe)* — call `pplx_sdk.llm.extract_many` against the enriched rows with criteria phrased as exclusions, per the recipe.
5. **Score candidates** *(this skill)* — score the surviving candidates, then check each against the SQLite store and Ashby exclusions. Apply score caps from `scoring_and_feedback.md`.
6. **Save to database** *(this skill)* — write new candidates, scored fields, recency signals, company tier, tenure data, dedupe status to the canonical SQLite store.
7. **Build review payload** *(this skill)* — read SQLite back into the structured `ReviewBundle` shape from `schemas.py`.
8. **Render review UI** *(this skill)* — call `formatting.py --input bundle.json --output dist/`. Treat any validation warnings as a soft block — surface them in the workflow run summary.
9. **Scaffold review API** *(this skill — MANDATORY)* — call `scripts/scaffold_review_app.py --bundle bundle.json --output review-app/` to scaffold a SQLite-backed Express + better-sqlite3 review app from `server-template/`. Then `cd review-app && npm install`. **Skipping this step leaves the workflow with no persistence path; the rendered HTML alone is a non-persistent visual preview.**
10. **Seed review database** *(this skill — MANDATORY)* — `node scripts/seed.js public/review_bundle.json` loads candidates + runs + feedback themes + Ashby exclusions + hired seed profiles + workflow settings + general feedback into SQLite. Use `node scripts/seed.js --reset public/review_bundle.json` to drop prior reviewer state (use for a fresh role / brand-new run); default behavior preserves `review_state`, `status`, and `feedback` across reseeds so re-sourcing refreshes candidate metadata without wiping reviewer decisions.
11. **Start review app** *(this skill — MANDATORY)* — `npm start` from inside `review-app/`. The frontend then **fetches every read endpoint at startup** (`/api/candidates`, `/api/candidates/{ref}`, `/api/runs`, `/api/feedback-themes`, `/api/ashby-exclusions`, `/api/hired-seed-profiles`, `/api/general-feedback`, `/api/workflow-settings`) and writes every reviewer action (`PATCH /api/candidates/{ref}`, `PUT /api/general-feedback`). The endpoint shape matches the `ppl-ai/people-search-ui` reference.
12. **Publish for reviewer** *(workflow — MANDATORY for reviewer-facing deployment)* — follow the canonical static-frontend-plus-sandbox-proxied-backend recipe in `pplx/python/apps/asi/skills/website-building/webapp/SKILL.md` and `pplx/python/apps/asi/skills/website-building/shared/19-backend.md`, with these workflow-specific bindings: `start_server port=3000` and `deploy_website path=review-app/public entry_point=index.html`. Post the resulting URL to the reviewer via Slack / Sheet as configured in `WorkflowSettings`. Skipping `start_server` or publishing the review-app root instead of `public/` surfaces `Save failed — retry` on every reviewer click.
13. **Verify the backend through the deployed origin** *(this skill — MANDATORY before sharing the URL)* — confirm the BE is actually working, not just the static UI. Hit each `GET /api/*` endpoint at the deployed origin and confirm it returns the seeded SQLite data (not the embedded bootstrap snapshot). Then exercise `PATCH /api/candidates/{ref}` with `{review_state, feedback}` and `PUT /api/general-feedback` with `{content}` and confirm both writes succeed with 2xx, return the persisted row, and round-trip through a follow-up `GET`. A backend that serves reads but silently drops writes is broken and must be fixed before the URL is shared — see the "Backend is non-negotiable" section of `references/recruiting_ui_contract.md` for the full checklist.
14. **Collect feedback** *(workflow)* — reviewer decisions and free-text feedback are persisted by the review-app API into SQLite as they happen. Theme extraction runs over the new feedback before the next run.

## What this skill owns vs the `search` skill vs the workflow

- **`search` skill (+ `recipes/people-research.md`)**: every search/enrich/filter primitive — `pplx_sdk.search.people`, `pplx_sdk.search.web`, `pplx_sdk.content.fetch_many`, `pplx_sdk.content.snippets`, `pplx_sdk.llm.extract_many`, and the parallel-search / resumable-run patterns that drive them. The SDK contract and the canonical sourcing recipe.
- **This skill (`recruitment/automated-sourcing`)**: SQL-shaped JSON export contract, deterministic normalization, score / cadence / label rules, the HTML/CSS/JS review templates, the renderer (`formatting.py`), and the **review-app server template + scaffold script** that emits a SQLite-backed API every workflow run.
- **Workflow**: sourcing orchestration / scheduling, hosting the scaffolded review-app, Slack/Sheet IO, feedback theme extraction, secrets, ATS integration.

## Failure modes

- **Missing scores** — renderer emits warning; the workflow should not publish until scores are populated.
- **Duplicate `candidate_id`** — renderer emits warning; SQLite query likely deduped incorrectly.
- **Unknown cadence value** — renderer falls back to `manual`. Fix the workflow setting to one of the documented values.
