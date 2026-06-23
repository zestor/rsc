# Feature Spec

## PRD Structure

A PRD should contain these sections in order:

1. **Problem Statement** — Who has the problem, how often, what is the cost of not solving it. Ground in evidence (research, support data, metrics).
2. **Goals** — 3-5 measurable outcomes. Distinguish user goals from business goals. Outcomes, not outputs ("reduce time to first value by 50%" not "build onboarding wizard").
3. **Non-Goals** — 3-5 things explicitly out of scope with rationale. Prevents scope creep.
4. **User Stories** — Standard format: "As a [specific user type], I want [capability] so that [benefit]." Include edge cases and multiple personas. Order by priority.
5. **Requirements** — Categorized as P0/P1/P2 (see MoSCoW below). Each with acceptance criteria and dependency flags.
6. **Success Metrics** — Leading indicators (adoption, activation, task completion, error rate) and lagging indicators (retention, revenue, NPS, support ticket reduction). Set specific targets with measurement method and evaluation timeline.
7. **Open Questions** — Tagged with owner and blocking vs. non-blocking.

## MoSCoW Categorization

- **Must have (P0)**: Cannot ship without. "If we cut this, does the feature still solve the core problem?" If no, P0.
- **Should have (P1)**: Important but core use case works without them. Typically fast follow-ups.
- **Could have (P2)**: Desirable if time permits. Will not delay delivery if cut.
- **Won't have**: Explicitly out of scope. Documented to guide future design decisions.

If everything is P0, nothing is P0. Challenge every must-have.

## Acceptance Criteria

Write in Given/When/Then format:

- Given [precondition]
- When [action]
- Then [expected outcome]

Cover happy path, error cases, edge cases, and negative test cases. Every criterion independently testable. Avoid ambiguous words ("fast", "intuitive") — define concretely.

## User Story Quality Checklist (INVEST)

- **Independent**: Can be developed and delivered on its own
- **Negotiable**: Details can be discussed
- **Valuable**: Delivers value to the user
- **Estimable**: Team can roughly estimate effort
- **Small**: Completable in one sprint
- **Testable**: Clear verification method

Common mistakes: too vague ("make it faster"), solution-prescriptive ("add a dropdown"), no benefit stated, too large, internal-focus ("refactor the database").

## Gotchas

- **Non-goals are as important as goals** — Unstated non-goals become scope creep. Stakeholders will fill the ambiguity with their own expectations.
- **Acceptance criteria are a contract** — Vague criteria ("it should be fast") cause engineering/PM friction at review time. Invest the time upfront.
- **Success metrics need a baseline** — Setting targets without knowing current state is guessing. Measure the baseline before launch.
- **P1 is not a parking lot** — P1 should be things you are confident you will build soon. Use "Won't have" for the wish list.
- **User stories are not tasks** — "As the engineering team, we want to refactor X" is a task. Stories describe user value.