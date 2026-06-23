# Scoring & Feedback

## What the UI renders today

The review UI renders the score **only as a 1-10 number** inside a circular score-ring badge (cyan/teal accent ring around a dark inner disc; ring colour shifts to red / amber / green per the band thresholds below). It does **not** render a score-breakdown panel and does **not** render feedback-reason dropdowns. The Feedback block in the candidate detail is a single free-text Notes textarea plus the Yes / Maybe / No decision buttons.

The following fields are accepted by `schemas.py` for backward compatibility but are **not surfaced in the UI**:

- `score_breakdown`
- `score_cap_reasons`
- `feedback_reason_codes`
- `feedback_reason_labels`

The renderer's view layer drops them from the rendered payload. Older bundles that populate them still load cleanly; new bundles can omit them.

If you need a UI surface for breakdowns or reason codes, update `schemas.py` and the renderer's view-building helpers first — do not assume any of the legacy fields will appear.

## Score band (1-10)

Used by the workflow when scoring candidates. The UI renders these directly:

- **10** — Excellent. Recent must-have experience, strong company/team signal, strong location fit, low risk.
- **9** — Strong. Minor caveat only.
- **8** — Good. One meaningful uncertainty.
- **7** — Maybe. Good signal but missing recency, domain, company, or tenure confidence.
- **≤ 6** — Do not send by default.

## Score caps (workflow-internal)

These caps are **workflow-internal scoring rules**, not UI affordances. The workflow may still populate `score_cap_reasons` in SQLite for audit / debugging, but the renderer ignores the field — it will not appear in the rendered HTML. The caps that the scoring step should apply:

- No recent must-have experience → max 8.
- Strongest evidence older than 5 years → max 7.
- Recent role switch under 3 months → max 8.
- Weak duplicate confidence → max 7 (or exclude).
- Weak company signal for a company-sensitive role → max 8.
- Location uncertainty → max 8.
- Prior internal employment → special flag, not normal scoring.

## Feedback (workflow-internal)

The UI captures the reviewer decision (Yes / Maybe / No) and an optional free-text note. There is **no UI dropdown for reason codes**. If the workflow chooses to keep its own closed-set classification of reviewer feedback internally, that mapping lives in the workflow's own code; the renderer's `feedback_reason_codes` / `feedback_reason_labels` fields are silently dropped.

For historical reference, prior workflow revisions used these codes for an upstream classifier (not for the UI):

**Yes**: `strong_recent_relevant_experience`, `strong_company_team_signal`, `strong_systems_backend_fit`, `strong_domain_fit`, `good_seniority`, `good_location_fit`.

**No**: `not_recent_enough`, `weak_company_signal`, `wrong_domain`, `too_senior`, `too_junior`, `recent_role_switch`, `duplicate_already_known`, `weak_evidence`, `location_mismatch`.

**Maybe**: `strong_profile_unclear_recency`, `strong_company_weak_domain_fit`, `strong_domain_weak_company_signal`, `good_background_tenure_concern`, `needs_hiring_manager_judgment`.

These are not part of the rendered UI surface.

## Feedback themes

Themes are derived from per-candidate and general feedback by an upstream LLM step. The renderer displays them as cards in the bottom Feedback themes section. Each theme should declare:

- `detected_in_run_id` — the run whose feedback produced the theme.
- `applied_to_run_id` — the next run that used the theme (null until applied).
- `source` — `candidate` or `general` or `system`.
- `example_candidate_ids` — concrete examples for the reviewer.

The renderer never surfaces the raw upstream blob; it formats source label, run, date, theme label, and optional action. See `references/recruiting_ui_contract.md` for the exact pre-baked theme `view`.

## What the UI never decides

The UI does not change scores, persist feedback, or trigger runs. It is a read-only snapshot plus a local form for the reviewer's working state. All persistence flows back through the workflow.
