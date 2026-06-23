# Roadmap Management

## Roadmap Formats

**Now / Next / Later**: Simplest and most versatile. Now = committed (current sprint/month), Next = planned (1-3 months), Later = directional (3-6+ months). Best for external and leadership communication because it avoids false date precision.

**Quarterly Themes**: 2-3 themes per quarter mapped to OKRs. Each theme groups related initiatives. Good for showing strategic alignment and explaining why you are building what you are building.

**Timeline / Gantt**: Calendar-based with start/end dates and dependencies. Use for execution planning with engineering. NOT for external communication (creates false precision expectations).

## Prioritization Frameworks

### RICE Score

RICE = (Reach x Impact x Confidence) / Effort

- **Reach**: Concrete number of users affected per time period
- **Impact**: 3 = massive, 2 = high, 1 = medium, 0.5 = low, 0.25 = minimal
- **Confidence**: 100% = data-backed, 80% = some evidence, 50% = gut feel
- **Effort**: Person-months across all functions

Best for: quantitative comparison of a large backlog. Less useful for strategic bets where impact is hard to estimate.

### ICE Score

ICE = Impact x Confidence x Ease (each scored 1-10)

Simpler than RICE. Best for: quick prioritization, early-stage products, insufficient data for RICE.

### Value vs. Effort Matrix

- High value, low effort = quick wins (do first)
- High value, high effort = big bets (plan carefully)
- Low value, low effort = fill-ins (spare capacity)
- Low value, high effort = money pits (remove from backlog)

## Dependency Types

- **Technical**: Feature B requires infrastructure from Feature A
- **Team**: Requires work from another team (design, platform, data)
- **External**: Waiting on vendor, partner, or third-party
- **Knowledge**: Need research or investigation results before starting
- **Sequential**: Must ship A before starting B (shared code, user flow)

For each dependency: assign an owner, set a "need by" date, build buffer, and have a contingency plan.

## Capacity Planning

Engineers typically spend 60-70% of time on planned feature work after overhead (meetings, on-call, interviews, PTO).

Healthy allocation: 70% planned features, 20% technical health (debt, reliability, performance), 10% unplanned buffer. Adjust ratios for team context (new product = more features, post-incident = more reliability).

When roadmap commitments exceed capacity: cut scope, do not pretend people can do more. For every addition, ask "What comes off?"

## Gotchas

- **RICE scores create false objectivity** — Teams game the inputs to get their preferred project to the top. Use frameworks to structure discussion, not replace judgment.
- **Gantt charts imply promises** — Showing a date to a stakeholder, even with caveats, becomes a commitment in their mind. Use Now/Next/Later for anything uncertain.
- **20% tech debt allocation erodes silently** — Urgent feature work absorbs the tech debt budget unless it is explicitly protected. Treat it as non-negotiable.
- **Dependencies are the #1 roadmap risk** — Cross-team dependencies slip more often than scope or effort estimates. Flag them early and build buffer.
- **Roadmap changes without communication destroy trust** — When priorities shift, tell affected stakeholders directly. Do not let them discover it by noticing their project disappeared.