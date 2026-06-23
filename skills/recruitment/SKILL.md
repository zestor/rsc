# Recruitment

Index for recruiting / candidate-pipeline sub-skills.

## Sub-skills

- `recruitment/automated-sourcing` — useful when operating an end-to-end automated sourcing run with SQLite-backed candidate state, Ashby exclusions, and a backend-driven review UI (running, scheduling, debugging, rebuilding, deploying, or modifying that workflow). Not useful for generic candidate lookups, one-off people search, or reviewing yesterday's candidates — those should use `entity-search/people-search` or a direct query.
- `recruitment/github-profile-quality` — useful when scoring, ranking, or auditing a known list of GitHub developer profiles for technical hiring (two-pass: activity signals + source-code review). Not useful for finding candidates by role/location (use `entity-search/people-search`) or for running the persistent sourcing workflow (use `recruitment/automated-sourcing`).
- `recruitment/talent-pool-rendering` — explicitly invoked / workflow-internal renderer for static Talent Pool preview HTML from a `TalentPoolBundle` JSON (deterministic stdlib-only renderer; no backend, no SQLite, no API).

Shared design tokens consumed by recruitment preview UIs live under `recruitment/shared/ui/` (not directly loadable). Sub-skill renderers copy `tokens.css` into their output bundle.

To load a sub-skill: `load_skill(name="recruitment/<sub-skill>")`.