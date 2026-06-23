# automated-sourcing review-app server template

SQLite-backed Express server that the Automated Sourcing workflow scaffolds into a
review-app directory at runtime. This template is **emitted verbatim** into the
target review-app project by `scripts/scaffold_review_app.py` from the parent
skill — do not modify it in place per run. To change the runtime contract, edit
this template and re-scaffold.

## Endpoint contract

The frontend (`recruiting_review_app.js`) reads every read endpoint at startup
and re-renders against the API response. The embedded `review-bundle` JSON in
`recruiting_review_app.html` is only a bootstrap fallback for the static visual
preview — when the API is reachable, the UI overrides everything from it with
live values.

| Endpoint | Method | Body | Effect |
|---|---|---|---|
| `/api/candidates` | `GET` | — | List rows (id, candidate_id, full_name, headline, company, title, location, profile_url, score, predicted_rating, review_state, status, feedback, sourcing_run pointers). Capped at 500. |
| `/api/candidates/{ref}` | `GET` | — | Full row by integer `id`, `candidate_id`, or `profile_url`. Merges the `bundle_blob` (evidence bullets, concerns, draft outreach, view payload, etc.) with the live reviewer columns (`review_state`, `status`, `feedback`). |
| `/api/candidates/{ref}` | `PATCH` | `{ review_state?, status?, feedback? }` | Upsert reviewer's decision and notes. `review_state ∈ {yes, maybe, no, pending}`. Status auto-maps `yes\|maybe → reviewed`, `no → rejected`. Returns the merged row. |
| `/api/general-feedback` | `GET` | — | Workflow-wide free-text. |
| `/api/general-feedback` | `PUT` | `{ content }` | Replace workflow-wide free-text. |
| `/api/runs` | `GET` | — | Sourcing runs (run_id, label, started_at, completed_at, run_number). |
| `/api/feedback-themes` | `GET` | — | Theme rows extracted from prior reviewer feedback. |
| `/api/ashby-exclusions` | `GET` | — | Ashby exclusions used by the bottom panel. |
| `/api/hired-seed-profiles` | `GET` | — | Positive-signal seed profiles. |
| `/api/workflow-settings` | `GET` | — | Cadence / batch / channels / status object. |

Endpoint shape matches the [`ppl-ai/people-search-ui`](https://github.com/ppl-ai/people-search-ui)
reference where they overlap; automated-sourcing adds the per-candidate `bundle_blob`
expansion on the `GET /api/candidates/:ref` path so the detail panel can show
evidence/concerns/draft outreach without a second roundtrip.

## Run

```bash
npm install
node scripts/seed.js review_bundle.json   # populates every table from the workflow's bundle
npm start                                  # listens on 0.0.0.0:3000 by default
```

`scripts/seed.js --reset review_bundle.json` drops the existing reviewer state
(use for a fresh run); the default behavior preserves `review_state`, `status`,
and `feedback` across reseeds so a workflow run that re-sources can refresh
candidate metadata without wiping reviewer decisions.

Env:
- `PORT` (default `3000`) — the agent runtime / `start_server` proxy expects 3000.
- `HOST` (default `0.0.0.0`) — binds all interfaces so the sandbox port proxy can reach the process. Override to `127.0.0.1` only for local-only testing.
- `DB_PATH` (default `./data/candidates.db`)
- `RATE_LIMIT_DISABLED=1` to disable rate limiting in test harnesses.

`/api/*` responses include permissive CORS headers so a statically-deployed
frontend on a different origin can call the proxied sandbox backend.

## Deploying for a reviewer (the only mode that persists writes)

The rendered `public/` directory is the static frontend. The Express server is
the API backend. They must be deployed together:

```bash
npm install
node scripts/seed.js public/review_bundle.json
npm start              # listening on 0.0.0.0:3000
# then in the same sandbox session
start_server port=3000 # proxies a public URL to localhost:3000
deploy_website path=public entry_point=index.html
```

The rendered `recruiting_review_app.js` resolves its API base from the
`__PORT_3000__` token. `deploy_website` rewrites that token to the proxy
path so the deployed page calls back to the running Express server. Without
`start_server` the proxy is missing and reviewer clicks surface
`Save failed — retry`.

**Do not** upload the entire review-app root to a static host — only `public/`.
The API runs in the sandbox process and is reached over the port proxy.
