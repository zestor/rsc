# Create an Asset

Generate a tailored, customer-ready sales asset from deal context.

> For web-based formats (landing pages), use the `website-building` skill for all visual design and styling. This skill's visual design (in `references/visual-design.md`) applies to non-web outputs only.

## Execution Flow

1. Detect seller context from user's email domain (ask if ambiguous)
2. Collect inputs: prospect, audience, purpose, format
3. Research prospect (adaptive depth based on context richness)
4. Ask up to 2 rounds of clarifying questions
5. Build and deliver self-contained HTML asset

## Format Selection

| Format                           | Best For                                           |
| -------------------------------- | -------------------------------------------------- |
| **Interactive landing page**     | Exec alignment, intros, multi-tab value prop       |
| **Deck-style**                   | Formal presentations, large audiences              |
| **One-pager**                    | Leave-behinds, quick summaries                     |
| **Workflow / Architecture demo** | Technical deep-dives, POC demos, integration flows |

## Required Inputs

| Input            | What to Collect                                                          |
| ---------------- | ------------------------------------------------------------------------ |
| **(a) Prospect** | Company, key contacts, deal stage, pain points, uploaded materials       |
| **(b) Audience** | Exec / Technical / Ops / Mixed + primary concern                         |
| **(c) Purpose**  | Intro / Follow-up / Deep-dive / Alignment / POC / Close + desired action |
| **(d) Format**   | One of the four formats above                                            |

## Audience Adjustments

- **Executive**: lead with business impact, ROI, strategic alignment
- **Technical**: lead with architecture, security, integration depth
- **Operations**: lead with workflow impact, change management, support
- **Mixed**: use tabs or sections to separate depth levels

## Content Principles

- Reference specific pain points from transcripts or user input
- Use the prospect's language and terminology
- Map seller capabilities to prospect needs explicitly
- Include proof points (case studies, metrics) where available
- Every section should feel tailored, not templated

## Structure by Purpose

| Purpose                 | Recommended Sections                                                         |
| ----------------------- | ---------------------------------------------------------------------------- |
| **Intro**               | Company Fit, Solution Overview, Key Use Cases, Why Us, Next Steps            |
| **Discovery follow-up** | Their Priorities, How We Help, Relevant Examples, ROI Framework, Next Steps  |
| **Technical deep-dive** | Architecture, Security & Compliance, Integration, Performance, Support       |
| **Exec alignment**      | Strategic Fit, Business Impact, ROI Calculator, Risk Mitigation, Partnership |
| **POC proposal**        | Scope, Success Criteria, Timeline, Team, Investment, Next Steps              |

## Workflow Demos

See `references/workflow-demo-schema.yaml` for component types and step definitions. When the user selects this format, parse their description for systems, data flows, and human touchpoints before asking follow-up questions.

## Visual Design (Non-Web)

See `references/visual-design.md` for color system, typography, and component styling. Extract prospect brand colors from their website; fall back to industry defaults if unavailable.

## Output

- Self-contained HTML file (all CSS/JS inline, no external deps except Google Fonts)
- File naming: `[ProspectName]-[format]-[date].html`

## Gotchas

- **Seller context detection can misfire** -- multi-product companies and consultants need explicit disambiguation; don't guess.
- **Max 2 rounds of questions** -- if still ambiguous after two rounds, make a reasonable choice and note the assumption.
- **Transcripts are the best input** -- raw call recordings or meeting notes produce far better assets than second-hand summaries.
- **One-pagers must stay on one page** -- resist the urge to add sections; the constraint is the feature.
- **Brand color extraction is fragile** -- websites with complex CSS may yield wrong colors; always confirm with the user.