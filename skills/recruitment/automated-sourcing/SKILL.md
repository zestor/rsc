# Automated Sourcing

## Routing boundary

Load this skill only when the user asks to operate or change the Automated Sourcing workflow itself.

Good triggers include:

- run a new or existing automated-sourcing run;
- do the next automated-sourcing run;
- schedule recurring automated-sourcing runs;
- rebuild or redeploy the automated-sourcing review UI;
- fix automated-sourcing API writeback or SQLite persistence;
- sync Ashby exclusions or hired seed patterns for an automated-sourcing run;
- regenerate the backend-driven review app from a workflow export;
- modify automated-sourcing workflow code, templates, schemas, renderer, or server scaffold.

Mentioning `Automated Sourcing`, `automated-sourcing`, `automated sourcing`, or `candidate sourcing` by name is not enough. The request must be about running, scheduling, debugging, rebuilding, deploying, or modifying the persistent workflow.

Do not load this skill for one-off candidate searches, people lookups, recruiter contact searches, or general profile research, even if the prompt includes a job description, candidate criteria, scoring, or the word "source". Those should use `entity-search/people-search`.

Do not load for drafting, editing, proofreading, or reviewing Slack/email/announcement copy about Automated Sourcing, even if the message asks people to test or give feedback on the tool. Writing communications is not running, debugging, or modifying the workflow.

Do not load this skill for product feedback summaries, UX planning, recruiter feedback analysis, recruiting strategy, ATS comparisons, PR/eval help, or general discussion about the Automated Sourcing workflow. Do not load any sub-skill for those unless the user explicitly asks to run, debug, rebuild, schedule, or modify the workflow.

This skill owns the **recruitment workflow** on top of the `search` skill's people-research recipe:

- read the role definition, prior reviewer feedback, and the run cadence;
- run the sourcing pass by following `search/recipes/people-research.md` (search → enrich → filter → optional dossier) on the `pplx_sdk` people / web / content / llm modules, do not duplicate those primitives;
- normalize and persist candidates to SQLite (the canonical store);
- regenerate the static review UI bundle from the SQLite export via `formatting.py` and `templates/`;
- surface reviewer decisions (Yes / Maybe / No) and free-text notes for the next run to ingest.

The `search` skill is already loaded alongside this one and owns every people-search / search / enrich / filter primitive used during a sourcing pass. Automated Sourcing **delegates** those to the search skill's people-research recipe and does not reimplement them; refer to the already-loaded `search` skill for the current procedure rather than naming its internal files here.

For a single one-off named lookup ("find Jane Doe at Acme", "senior PMs at Google"), use `entity-search/people-search`. Pick automated-sourcing only for the recurring workflow with persistence, scoring, and review-UI regeneration.

## Pipeline

```text
       role brief + reviewer feedback
                    │
                    ▼
   load_skill("search") + follow
   search/recipes/people-research.md
   (search → enrich → filter → dossier)
                    │
                    ▼
       structured candidate list
                    │
                    ▼
       SQLite (canonical store)
                    │
                    ▼
   JSON export shaped by schemas.py (ReviewBundle)
                    │
                    ▼
   formatting.py (deterministic renderer)
                    │
                    ▼
   templates/recruiting_review_app.{html,css,js}
                    │
                    ▼
       static UI bundle (HTML + CSS + JS + JSON)
                    │
                    ▼
   scripts/scaffold_review_app.py
   (emits server-template/ + UI bundle into review-app/)
                    │
                    ▼
   node scripts/seed.js review_bundle.json
   (loads candidates + runs + themes + exclusions
    + seeds + workflow settings + general feedback
    into SQLite, every workflow run reseeds)
                    │
                    ▼
   review-app/ — Express + better-sqlite3
   GET /api/candidates, /api/candidates/{ref}, /api/runs,
   /api/feedback-themes, /api/ashby-exclusions,
   /api/hired-seed-profiles, /api/general-feedback,
   /api/workflow-settings
   PATCH /api/candidates/{ref}, PUT /api/general-feedback
   serves the rendered UI; the UI fetches every read on
   startup and PATCHes every reviewer click
```

## Rules

> **Source of truth for UI surface rules: `references/recruiting_ui_contract.md`.** The UI-surface bullets below (what is and isn't rendered, score band, Ashby surface format, the Google Fonts caveat) are a fast index of that reference. If they disagree, the reference wins. Update the reference first, then resync this list. The composition / SQLite / no-LLM-string-insertion rules live here in `SKILL.md`; do not look for them in the UI contract.

- **Reuse the search recipe, don't fork it.** Every search / enrich / filter call goes through the `search` skill, and the procedure is the one in `search/recipes/people-research.md`. This skill should not introduce its own `pplx_sdk.search.*` recipes. If sourcing requires new behavior (a new filter kwarg, a new web-search fallback, a different fan-out shape), land it in `search/` or the people-research recipe and consume it here.
- **Data contract lives in `schemas.py`** — every JSON export must conform to the `ReviewBundle` dataclass. The contract covers candidates, runs, feedback themes, general feedback, Ashby exclusions, hired seed profiles, and workflow settings/cadence. Forward-compatible recency/domain/company-tier/tenure/internal-history/dedupe fields are present as optional fields; existing payloads keep working.
- **SQLite is the source of truth, and the workflow review UI is fully backend-driven.** Every workflow run (a) scaffolds the review-app server from `server-template/` via `scripts/scaffold_review_app.py`, (b) seeds the SQLite store from the just-rendered `review_bundle.json` via `scripts/seed.js`, and (c) deploys the running server. The frontend `recruiting_review_app.js` then **fetches every read endpoint at startup** (`GET /api/candidates`, `/api/candidates/{ref}`, `/api/runs`, `/api/feedback-themes`, `/api/ashby-exclusions`, `/api/hired-seed-profiles`, `/api/general-feedback`, `/api/workflow-settings`) and writes every reviewer action (`PATCH /api/candidates/{ref}` with `{review_state, status?, feedback?}`, `PUT /api/general-feedback` with `{content}`) — endpoint shape matches the [`ppl-ai/people-search-ui`](https://github.com/ppl-ai/people-search-ui) reference. Any non-2xx or network failure surfaces `Save failed — retry` (red `.save-error`); the UI never silently saves to browser memory. **The renderer's `formatting.py --output dist/` artifact alone is a non-persistent visual preview** — the embedded `<script id="review-bundle">` JSON is a bootstrap fallback for screenshot / smoke-render only and must not be deployed as the workflow review UI. Production workflow review = run the scaffolded server; everything else is a preview.
- **Templates live in `templates/`** — HTML, CSS, and JS are checked-in assets. Edit them in this skill, not in the workflow's own repo. Never hand-author a one-off HTML page for a new run.
- **The renderer is deterministic** — `formatting.py` itself is stdlib-only Python and pure: same `ReviewBundle` input → byte-identical UI bundle output. Normalization (1-10 score band, human-readable run labels, deduped Ashby exclusion labels, feedback theme display, cadence labels with timezone + scheduled / manual status, role-subtitle deduplication) happens in code, not in prompts. The generated HTML bundle references an external font CDN (Inter / Geist Mono via Google Fonts) for typography; the CSS declares a full system-font fallback so the UI degrades cleanly when the network is unavailable. Consumers that need a fully air-gapped preview can vendor the font files or strip the `<link>` tag — see the note in the `formatting.py` module docstring.
- **UI conventions are fixed** — the rendered UI keeps Yes / Maybe / No (no Skip) at the top of the candidate detail; Feedback themes and Ashby exclusions sit at the bottom of the page; each list card carries the candidate's LinkedIn / profile link in addition to the detail view; scores are only displayed on a 1-10 scale; the save-status copy is `Saved`. Candidates can be grouped by review state or by found run via the Group-by control.
- **No feedback-reason dropdowns, no score breakdowns, no quality-threshold display** — the UI intentionally does not surface feedback reason codes, score breakdowns, or a workflow quality threshold. The `Feedback` block at the bottom of the detail is a single notes textarea. Those fields may still exist on the schema as backward-compatible optional inputs but are not rendered or required.
- **No LLM string-insertion into HTML** — the LLM produces structured JSON, the renderer produces the HTML. If a new field is needed in the UI, add it to `schemas.py` first.
- **No real candidate PII in sample data** — if you ship sample fixtures, they must be synthetic.

When the Automated Sourcing workflow finishes a run, the calling agent must:

1. Export a `ReviewBundle` JSON from SQLite (matching `schemas.py`).
2. Render the UI bundle with `formatting.py`.
3. **Scaffold, seed, start, and deploy the review-app server** with `scripts/scaffold_review_app.py`, `node scripts/seed.js`, `npm start`, and the `start_server` → `deploy_website` proxy flow. This is the mandatory API-generation step.
4. **Verify the backend end-to-end through the deployed origin before sharing the URL with a reviewer.** Hit each `GET /api/*` endpoint and confirm it returns seeded SQLite data (not the bootstrap snapshot), then exercise `PATCH /api/candidates/{ref}` and `PUT /api/general-feedback` and confirm the writes round-trip via a follow-up `GET`. A static UI without a working API is **not** a valid review surface — every reviewer click would render `Save failed — retry` and persist nothing. See the **"Backend is non-negotiable — the BE must always work"** section at the top of [`references/recruiting_ui_contract.md`](references/recruiting_ui_contract.md) for the full checklist; do not hand out the review URL until every item passes.

Do not produce review HTML directly from prompts. Go through the renderer so the conventions above are guaranteed.

### Render the UI

```bash
python3 pplx/python/apps/asi/skills/recruitment/automated-sourcing/formatting.py \
    --input /path/to/review_bundle.json \
    --output /path/to/dist/
```

### Scaffold the SQLite-backed review app (REQUIRED for workflow use)

```bash
python3 pplx/python/apps/asi/skills/recruitment/automated-sourcing/scripts/scaffold_review_app.py \
    --bundle /path/to/review_bundle.json \
    --output /path/to/review-app/

cd /path/to/review-app/
npm install
node scripts/seed.js public/review_bundle.json
npm start  # binds 0.0.0.0:3000, Yes/Maybe/No persists to SQLite
```

The scaffold copies `server-template/` (Express + better-sqlite3, modeled on `ppl-ai/people-search-ui`) into `review-app/`, drops the rendered UI bundle into `review-app/public/`, and prints the run instructions. The server exposes the full read+write endpoint surface (`GET /api/candidates`, `GET /api/candidates/{ref}`, `GET /api/runs`, `GET /api/feedback-themes`, `GET /api/ashby-exclusions`, `GET /api/hired-seed-profiles`, `GET /api/general-feedback`, `GET /api/workflow-settings`, `PATCH /api/candidates/{ref}`, `PUT /api/general-feedback`); the rendered JS fetches every read at startup and PATCHes every reviewer click. The embedded `<script id="review-bundle">` JSON in the HTML serves only as a bootstrap fallback so the visual preview renders when no API is reachable.

For a fresh run that drops the prior reviewer state, add `--reset`: `node scripts/seed.js --reset public/review_bundle.json`. Default behavior preserves `review_state`, `status`, and `feedback` columns across reseeds so re-running sourcing refreshes candidate metadata without wiping the reviewer's work.

If `--ui-bundle` is omitted, the scaffold script renders the UI from `--bundle` itself in one step.

### Deploying the review UI so reviewers outside the sandbox can use it

Deployment follows the canonical static-frontend + sandbox-proxied-backend recipe in `pplx/python/apps/asi/skills/website-building/webapp/SKILL.md` (and `pplx/python/apps/asi/skills/website-building/shared/19-backend.md` for `__PORT_*__` token semantics). Workflow-specific bindings: backend is the scaffolded Express + better-sqlite3 server, port is **3000**, `dist_path` is `review-app/public`, entry is `index.html`.

```bash
cd /path/to/review-app/
npm install
node scripts/seed.js public/review_bundle.json
npm start                                # binds 0.0.0.0:3000
start_server port=3000
deploy_website path=public entry_point=index.html
```

## References

- [`search/recipes/people-research.md`](../../search/recipes/people-research.md) — **read before running the sourcing pass.** Canonical search → enrich → filter → optional dossier recipe that powers steps 1-4 of the workflow; Automated Sourcing delegates to it rather than duplicating it.
- `references/candidate_sourcing_workflow.md` — **read before planning or running a workflow run.** End-to-end procedure: role intake, sourcing pass via the search recipe, scoring, SQLite write-back, review-UI regeneration, review-app API scaffold, reviewer-feedback ingest for the next run.
- `references/recruiting_ui_contract.md` — **read when changing, rendering, or scaffolding the review UI / API.** Exact rendered UI contract: layout, components, score-ring badge, runtime API contract (`PATCH /api/candidates/{ref}` + `PUT /api/general-feedback`), and the font-dependency caveat.
- `references/scoring_and_feedback.md` — **read when interpreting Yes / Maybe / No decisions or feedback themes.** Covers the 1-10 score band, how reviewer decisions feed back into future runs, and what each decision means in this workflow.
- `references/ashby_dedupe_rules.md` — **read before syncing or filtering Ashby exclusions.** Dedupe + normalization rules consumed by `formatting.normalize_ashby_exclusion`.
- `server-template/` — **read when modifying review-app backend endpoints or SQLite persistence.** The Express + better-sqlite3 review-app server template (`package.json`, `server/index.js`, `scripts/seed.js`, `README.md`). Edit here, not in any scaffolded copy.
- `scripts/scaffold_review_app.py` — **read when generating a review app for a run.** The mandatory API-generation step: stdlib-only Python CLI that copies `server-template/` + the rendered UI bundle into a target directory; the operator then runs `npm install && npm start`.