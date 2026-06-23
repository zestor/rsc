# Recruiting Review UI Contract

This reference defines the data contract between the Automated Sourcing workflow and the review UI rendered by `formatting.py`. The deployed workflow review UI is **backend-driven**: the rendered HTML/CSS/JS is served from `review-app/public/` and makes runtime API calls to the scaffolded Express + better-sqlite3 server for every read and every reviewer write. The same renderer also produces a **static visual preview** for screenshot/QA use that has no backing API; in that mode the embedded JSON serves as a bootstrap fallback only.

## Backend is non-negotiable — the BE must always work

**Static UI rendering is not sufficient for a workflow review.** A deployment that serves only the rendered `recruiting_review_app.{html,css,js}` (or any static-host preview) without the Express + better-sqlite3 backend behind it is **not a valid review surface** and MUST NOT be handed to a reviewer or linked from a workflow run.

Before the UI is considered ready, every workflow run MUST do all of the following:

- [ ] **Scaffold the backend.** Run `scripts/scaffold_review_app.py` to copy `server-template/` (Express + better-sqlite3) and the rendered UI bundle into `review-app/`.
- [ ] **Seed SQLite.** Run `node scripts/seed.js public/review_bundle.json` so candidates, runs, feedback themes, Ashby exclusions, hired seed profiles, workflow settings, and general feedback are all present in the SQLite store.
- [ ] **Start the backend.** Run `npm install && npm start` so the Express server is listening on `0.0.0.0:3000`.
- [ ] **Expose the backend through the port proxy.** Run `start_server port=3000` and `deploy_website path=public entry_point=index.html` so the deployed origin proxies `/api/*` to the running Express server (see `pplx/python/apps/asi/skills/website-building/shared/19-backend.md` for the `__PORT_3000__` token semantics).
- [ ] **Verify reads end-to-end.** Hit the deployed origin's `GET /api/candidates`, `GET /api/runs`, `GET /api/feedback-themes`, `GET /api/ashby-exclusions`, `GET /api/hired-seed-profiles`, `GET /api/general-feedback`, and `GET /api/workflow-settings`. Each must return a 2xx with the seeded data (not the bootstrap snapshot).
- [ ] **Verify writes end-to-end.** Hit `PATCH /api/candidates/{ref}` with a `{review_state, feedback}` body and `PUT /api/general-feedback` with a `{content}` body. Both must return 2xx, the persisted row must come back in the response, and a follow-up `GET` must read the new value back from SQLite. A backend that serves reads but silently drops writes is broken — Yes/Maybe/No and general feedback would not persist for the reviewer.

Only after every box above is checked is the UI ready to be shared with a reviewer. If any step fails, the workflow run must surface the failure rather than hand out a static-only URL: the reviewer experience on a static deploy is that **every click shows `Save failed — retry`** and no decision is persisted, which is worse than no UI at all.

The renderer's `formatting.py --output dist/` artifact alone is a non-persistent visual preview — use it for screenshots and visual QA only, never as the workflow review UI.

## Source of truth

SQLite remains the canonical store. In the deployed workflow review UI, the frontend issues runtime API calls (`GET /api/candidates`, `PATCH /api/candidates/{ref}`, `PUT /api/general-feedback`, etc.) against the Express server, which reads and writes that SQLite store directly — reviewer decisions are persisted by those API calls, not by re-running the workflow. The embedded `ReviewBundle` JSON inside `recruiting_review_app.html` is a bootstrap snapshot used only when the API is unreachable (the static visual preview); a deployment that serves it without a running API is non-persistent.

## Top-level payload

The renderer consumes a `ReviewBundle` (see `schemas.py`):

| Field | Notes |
|---|---|
| `schema_version` | Integer. Renderer tolerates older versions by treating new optional fields as empty. |
| `generated_at` | ISO 8601 string. Display-only; do not parse for behavior. |
| `role_label` | Short role title for the header. |
| `role_brief` | One-line context shown under the title. |
| `candidates` | `list[Candidate]` |
| `runs` | `list[Run]` |
| `feedback_themes` | `list[FeedbackTheme]` |
| `general_feedback` | `list[GeneralFeedback]` |
| `ashby_exclusions` | `list[AshbyExclusion]` — deduped at render time. |
| `hired_seed_profiles` | `list[HiredSeedProfile]` — synthetic reference profiles. |
| `workflow_settings` | `WorkflowSettings` — cadence, batch size, channels, etc. |

## Required candidate fields

`candidate_id`, `full_name`, and `score` should always be present. The renderer emits a validation warning otherwise.

## Optional but supported candidate fields

Recency: `recent_relevant_experience`, `recent_relevance_window`, `recent_relevance_score`.

Company: `company_quality_tier` (`tier_1` … `tier_4` or `unknown`), `company_quality_notes`.

Tenure: `current_role_start_date`, `current_role_tenure_months`, `tenure_risk` (`none|low|medium|high`), `tenure_notes`.

Internal history: `internal_history_status` (`none|prior_employee|current_employee|known_conflict|unknown`).

Dedupe: `ashby.check_status` (`checked|partial|unavailable`), `ashby.match_status` (`clear|possible_duplicate|excluded|unknown`), `ashby.match_confidence` (`high|medium|low|none`), `ashby.match_reason`.

Evidence: `evidence_bullets`, `concerns`, `main_reason_for_fit`, `main_concern`.

Outreach: `draft_outreach` (free text). Accepted in the schema and round-tripped through `bundle_blob`, but **not rendered** — the UI has no draft-outreach surface.

Links: `profile_url`, `profile_links` (a label→URL map; the renderer never includes raw internal IDs or Slack channel IDs from the payload — the workflow should not put private fragments here in the first place).

Backward-compatible inputs that are **not rendered**: `draft_outreach`, `score_breakdown`, `score_cap_reasons`, `feedback_reason_codes`, `feedback_reason_labels`. The dataclasses still accept these so older exports load cleanly, but the UI deliberately omits the draft-outreach block, the score-breakdown panel, and any feedback-reason dropdowns. Don't rely on them surfacing anywhere — they're ignored by the renderer's view layer.

## Renderer-applied normalization

- **Score band** — `score` is clamped to `[1, 10]` and rounded to one decimal. Inputs on 0-1 or 0-100 scales are projected. `raw_score` is preserved for debugging.
- **Run label** — `Run.label`, when missing, is derived from `run_id` and `started_at` as `Run YYYY-MM-DD HH:MM · <suffix>`.
- **Feedback theme** — `description` whitespace trimmed; `label` whitespace trimmed.
- **Ashby exclusion** — Exclusions are deduped by `(candidate_name, reason, status, excluded_at)`. Raw internal IDs are kept on the dataclass but never surfaced into the UI text. Repeated reason labels collapse to a single row.
- **Cadence label** — Unknown cadence values fall back to `manual`.

## Renderer-baked `view` payload

To keep the JS thin, the renderer embeds a `view` sub-object on each candidate, on `workflow_settings`, and on each Ashby exclusion, plus a top-level `view` object. These contain display-ready strings derived deterministically from the underlying fields:

- **`candidates[*].view`** — `score_display`, `score_band` (`strong|maybe|weak`), `predicted_rating_text` (e.g. `predicted 8.8/10`), `current_line` (`title · company · location`), `ashby_label` / `ashby_mood`, and a pre-built `tags: [{label, mood}]` array for the list-view chips (tenure, internal history, Ashby status, company tier, review state).
- **`workflow_settings.view`** — `scheduled_text` (`Scheduled` / `Manual only`), `cadence_label`, `channels_text`, `batch_text`, `threshold_text`, `last_run_text`, `next_run_text`, `timezone_text`, `status_text`, `is_scheduled` (boolean). Each falls back to `"—"` when absent.
- **`ashby_exclusions[*].view`** — `primary_line` (name), `secondary_line` (`reason · status`), `tertiary_line` (date).
- **`view.review_decision_labels`** — `{yes, maybe, no}` → human labels. No `skipped` entry — the skill UI does not surface a Skip button (Yes/Maybe/No only).
- **`view.save_label`** — `"Saved"`. Used by the JS for the inline save confirmation text after a decision is recorded.
- **`view.role_subtitle`** — the role brief with the role label de-duplicated (see below).
- **`view.group_by_options`** — list of `[value, label]` pairs for the Group-by control. The skill ships `review_state`, `found_run`, and `none`.
- **`view.default_group_by`** — `"review_state"`.
- **`view.run_labels`** — map of `run_id → human label` so the candidate feed can show "Found run" group headers without re-deriving labels client-side.

The skill's JS is backward-compatible: it falls back to computing these client-side when `view` is absent, so older bundles still render.

### Run cadence

`WorkflowSettings` carries the cadence detail the UI needs:

- `run_cadence` — `manual | hourly | daily | weekly | pause`.
- `cadence_scheduled` — boolean. `True` means the workflow is actively scheduled at the given cadence; `False` means the cadence value is informational but no scheduler is running. The renderer treats `manual` / `pause` as "Manual only" regardless of this flag.
- `timezone` — IANA TZ string (e.g. `America/Los_Angeles`) used to interpret `next_run_at` / `last_run_at`.
- `status_text` — optional free-form line ("On schedule — next run in ~12h.", "Last run failed — retrying", etc.) shown under the Workflow status card.
- `next_run_at`, `last_run_at`, `batch_size`, `quality_threshold`, `notification_channels` — as before.

### Role label / subtitle dedupe

The renderer drops the brief from the header subtitle when it starts with the role label (case-insensitive). This avoids the duplicated-role display seen when an export emits `Role: <title>` as the brief's first line.

### Headline / current-position dedupe

In the detail panel, the renderer hides `headline` when it is a token-level subset of the current line (`current_title · current_company · location`), ignoring joiner words (`at`, `in`, `for`, `of`, `the`, `and`). Otherwise the headline renders.

Template:

```
headline: <Title> · <Company> · <Location>
```

## UI surfaces

The HTML template `recruiting_review_app.html` provides two columns plus a bottom ops section:

1. **Candidate feed** — filterable, **groupable** list. Each row carries a small circular score-ring badge, quick tags for tenure / internal history / Ashby status / company tier / review state, **and a `LinkedIn` link on each card when a `profile_url` is present** (only the link text itself is clickable, and clicking the link opens the profile without changing selection). The feed's Group-by control toggles between Review state, Found run, and None.
2. **Detail panel** — review decision (Yes / Maybe / No at the top, with an inline `Saved` confirmation), a larger circular score-ring badge in the header, tags, main reason / main concern, evidence, concerns, and a Feedback section with a single free-text Notes textarea + Save & next button at the bottom of the detail card. Draft outreach is not surfaced in the UI (the field remains in the schema and `bundle_blob` for data compatibility, but is no longer rendered). The detail does not show a score-breakdown panel or feedback-reason checkboxes.
3. **Bottom ops section** — Workflow status, Hired seed profiles, General feedback, Feedback themes, and Ashby exclusions laid out below the candidate review area (the candidate list and details are no longer pushed right by a left sidebar). The section carries `id="ops-section"` so the header **"Show workflow data"** button (an anchor with `href="#ops-section"`, augmented by a small JS smooth-scroll handler) can scroll the user to it from the top of the page.

Keyboard shortcuts (handled in `recruiting_review_app.js`): `J/K` (or arrow keys) for next/previous, `Enter` to save-and-advance, `Y/N/M` to set the decision.

## Light/dark theme

`recruiting_review_app.css` defines a `data-theme="light"` default and a `data-theme="dark"` variant on `<html>`. The toggle button in the header swaps the attribute.

## Output bundle

The renderer writes the following files into `--output`:

- `recruiting_review_app.html`
- `recruiting_review_app.css`
- `recruiting_review_app.js`
- `review_bundle.json` (the normalized payload, useful for debugging or for an alternative client)

The HTML embeds a normalized `ReviewBundle` JSON in a `<script id="review-bundle" type="application/json">` tag. **That bundle is a bootstrap fallback only.** The frontend JS calls the API at startup and overrides every section of the in-memory state with the live values: candidates, runs, themes, exclusions, seeds, general feedback, workflow settings. When the API is reachable (the workflow review-app), the embedded bundle is never user-visible after the first paint. When the API is unreachable (a static-host preview), the bootstrap renders the snapshot for visual QA only and every click still attempts the API write and visibly fails.

Typography is an external dependency: the HTML links to Inter / Geist Mono from Google Fonts, with a full system-font fallback in the CSS so the UI still renders correctly offline. Consumers that need a fully air-gapped artifact should vendor the font files alongside the bundle or remove the `<link rel="stylesheet" href="https://fonts.googleapis.com/...">` tag from `recruiting_review_app.html`.

## Runtime API contract

The workflow review UI is **fully backend-driven**. The automated-sourcing skill ships a checked-in server template under `server-template/` and a scaffold script under `scripts/scaffold_review_app.py`; **every workflow run scaffolds, seeds, and starts a review-app server from these** — there is no production mode that serves only the static HTML.

| Endpoint | Method | Body | Effect |
|---|---|---|---|
| `/api/candidates` | `GET` | — | List candidates (read by the JS at startup for the feed). |
| `/api/candidates/{ref}` | `GET` | — | Full candidate row by integer `id`, `candidate_id`, or `profile_url` — includes the `bundle_blob` (evidence bullets, concerns, draft outreach, view payload) merged with live reviewer columns. Called on selection to hydrate the detail panel. (Draft outreach is preserved in the blob for back-compat but not rendered.) |
| `/api/candidates/{ref}` | `PATCH` | `{ review_state?, status?, feedback? }` — `review_state ∈ {yes, maybe, no, pending}` | Upsert reviewer's decision and / or notes into SQLite. **Called on every Yes/Maybe/No click and on Save-and-next.** |
| `/api/general-feedback` | `GET` | — | Workflow-wide free-text feedback. |
| `/api/general-feedback` | `PUT` | `{ content }` | Replace the workflow-wide free-text in SQLite. **Called on the "Save general feedback" button.** |
| `/api/runs` | `GET` | — | Sourcing runs (used by the "Group by → Found run" control and run-label rendering). |
| `/api/feedback-themes` | `GET` | — | Theme rows rendered in the bottom Feedback themes panel. |
| `/api/ashby-exclusions` | `GET` | — | Ashby exclusions rendered in the bottom Ashby panel. |
| `/api/hired-seed-profiles` | `GET` | — | Positive-signal seed profiles rendered in the bottom ops section. |
| `/api/workflow-settings` | `GET` | — | Cadence / batch / channels / status object rendered in the workflow-status card in the bottom ops section. |

The `unreviewed` value the UI uses internally maps to `pending` on the wire; the JS handles the translation in both directions (`wireReviewState` outbound, `reviewStateFromWire` inbound).

Write endpoints return `200 OK` with the persisted row JSON on success.

**Failure behavior is loud, not silent.** Any non-2xx response, network failure, or missing endpoint surfaces in the status line as `Save failed — retry` (red `.save-error` state) with the underlying error in the `title=` tooltip. The in-memory state is retained so the reviewer can retry, but the UI does not pretend the save succeeded. Workflow deployments that lack a working API see save errors on every click — that's the correct signal that the scaffold step was skipped or the server isn't running.

## Frontend bootstrap sequence

`recruiting_review_app.js` on `DOMContentLoaded`:

1. Parses the embedded `#review-bundle` JSON as `bundle` (preview-mode fallback).
2. Calls `renderAll()` once so even a no-API host still paints something for visual QA.
3. Awaits `bootstrapFromApi()` — fires all read endpoints in parallel via `Promise.allSettled`. Each fulfilled response overrides the corresponding `bundle.*` section in memory. If any read fails, `state.apiAvailable = false` and a console warning is logged; the bootstrap snapshot stays in place for that section.
4. Calls `renderAll()` again, now driven by API data when the API is up.

Selecting a candidate fires `GET /api/candidates/{ref}` in the background to hydrate the detail panel with the full row (including `bundle_blob` fields like evidence and concerns; `draft_outreach` is hydrated but not rendered). The hydration is best-effort: if it fails, the bootstrap snapshot keeps the detail panel populated.

### Generating the API (mandatory workflow step)

Every workflow run that intends a reviewer to use the UI MUST invoke:

```bash
python3 pplx/python/apps/asi/skills/recruitment/automated-sourcing/scripts/scaffold_review_app.py \
    --bundle /path/to/review_bundle.json \
    --output /path/to/review-app/

cd /path/to/review-app/
npm install
node scripts/seed.js public/review_bundle.json   # seeds candidates + runs + themes + exclusions + seeds + workflow settings + general feedback
npm start                                          # binds 0.0.0.0:3000
```

Use `node scripts/seed.js --reset public/review_bundle.json` for a fresh run that drops prior reviewer state. The default behavior preserves `review_state`, `status`, and `feedback` columns across reseeds.

### API base resolution and deployment

The rendered `recruiting_review_app.js` carries a `__PORT_3000__` token; the dev-vs-deploy resolution and the `start_server` → `deploy_website` flow are documented in `pplx/python/apps/asi/skills/website-building/shared/19-backend.md`. Workflow-specific bindings: port **3000**, `dist_path` `review-app/public`. The scaffolded server returns `Access-Control-Allow-Origin: *` on `/api/*` so the deployed origin can call the proxied backend.

### Static-render preview mode

`python3 formatting.py --input bundle.json --output dist/` writes a non-persistent visual preview suitable for screenshots, visual QA, and smoke-rendering. When the preview is opened directly from disk or served from a static file host with no API backend, the API reads fail and the UI renders from the embedded `#review-bundle` JSON; **clicking Yes/Maybe/No or Save displays the `Save failed — retry` error state** — the preview does not pretend to persist anything. Use this mode only for visual review, never as the production review UI.
