# Stakeholder Communications

## Audience-Specific Communication

**Executives**: Lead with the conclusion, not the journey. Status color + one-sentence TL;DR + progress against goals + risks needing their help + specific decisions with deadlines. Under 200 words. Only include risks you need help with.

**Engineering**: Link to specific tickets/PRs. Explain why when priorities change. Be explicit about blockers and what you are doing to unblock. Skip information that does not affect their work.

**Cross-functional partners** (design, marketing, sales, support): What is coming that affects them, what you need from them with deadlines, decisions that impact their work, open topics for feedback.

**Customers**: No internal jargon or ticket numbers. Frame everything as what they can now DO. Be honest about timelines without overcommitting. Only mention known issues if customer-impacting with a resolution plan.

## Green / Yellow / Red Status

- **Green**: On track. No significant risks. Use only when genuinely going well, not as default.
- **Yellow**: At risk. Mitigation underway but outcome uncertain. Flag at the FIRST sign of risk, not when sure things are bad.
- **Red**: Off track. Needs significant intervention (scope cut, resources, timeline extension). Use when you have exhausted your own options.

Move back to Green only when risk is genuinely resolved, not just paused.

## ROAM Risk Framework

- **Resolved**: No longer a concern. Document how.
- **Owned**: Acknowledged, someone actively managing. State owner and mitigation plan.
- **Accepted**: Proceeding without mitigation. Document rationale.
- **Mitigated**: Actions reduced risk to acceptable level. Document what was done.

When communicating risks: state clearly ("risk that X because Y"), quantify impact, state likelihood with evidence, present mitigation, make a specific ask.

## Decision Documentation (ADRs)

Write when: strategic product decisions, significant technical choices, controversial decisions where people disagreed, decisions that constrain future options, decisions you expect people to question later.

Structure: Status (Proposed/Accepted/Deprecated/Superseded) -> Context (forces at play) -> Decision (stated directly) -> Consequences (positive, negative, what it enables/prevents) -> Alternatives Considered (what, why rejected).

Write close to when the decision is made. Include who was involved. Document context generously — future readers lack today's context.

## Gotchas

- **Yellow is not a failure, it is good risk management** — Teams that are always green are hiding problems. Reward early risk flagging.
- **Risks communicated late become fire drills** — A risk flagged early is a planning input. The same risk flagged late is a crisis. There is no upside to waiting.
- **Status updates that list activities are useless** — "We had 14 standups and closed 23 tickets" tells leadership nothing. Report outcomes and progress against goals.
- **ADRs written weeks later miss critical context** — The rationale that felt obvious during the decision evaporates quickly. Write it same-day.
- **One update format for all audiences backfires** — Executives want strategic context in 200 words. Engineers want linked tickets. Customers want benefits. Rewriting for each audience is not optional.