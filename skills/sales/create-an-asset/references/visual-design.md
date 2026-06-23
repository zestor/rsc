# Visual Design Reference (Non-Web Formats Only)

For interactive landing pages and web-based formats, use the `website-building` skill instead.

Follow the **1 accent + neutrals** principle from `skills/design-foundations/SKILL.md`. The prospect's brand primary becomes the accent; everything else is neutral.

## Color System

```css
:root {
  --brand-primary: #[extracted from research];
  --brand-secondary: #[extracted];
  --brand-primary-rgb: [r, g, b];

  --bg-primary: #0a0d14;
  --bg-elevated: #0f131c;
  --bg-surface: #161b28;
  --bg-hover: #1e2536;

  --text-primary: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.7);
  --text-muted: rgba(255, 255, 255, 0.5);

  --accent: var(--brand-primary);
  --accent-hover: var(--brand-secondary);
  --accent-glow: rgba(var(--brand-primary-rgb), 0.3);

  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
}
```

## Typography

```css
font-family:
  'Inter',
  -apple-system,
  BlinkMacSystemFont,
  sans-serif;
h1: 2.5rem / 700;
h2: 1.75rem / 600;
h3: 1.25rem / 600;
body: 1rem / 400 / line-height 1.6;
small: 0.875rem / 500;
```

## Cards, Buttons, Animations

- Cards: `var(--bg-surface)`, 1px border rgba(255,255,255,0.1), 12px radius, hover elevation
- Primary buttons: `var(--accent)` bg, white text; Secondary: transparent, accent border
- Transitions: 200-300ms ease; tab switches: fade + slide

## Workflow Demo Nodes

```css
.node {
  background: var(--bg-surface);
  border: 2px solid var(--brand-primary);
  border-radius: 12px;
}
.node.active {
  box-shadow: 0 0 20px var(--accent-glow);
}
.node.human {
  border-color: #f59e0b;
}
.node.ai {
  background: linear-gradient(135deg, var(--bg-surface), var(--bg-elevated));
}
.arrow.active {
  stroke: var(--accent);
  stroke-dasharray: 8 4;
  animation: flowDash 1s linear infinite;
}
```

## Brand Color Fallbacks

| Industry      | Accent               |
| ------------- | -------------------- |
| Technology    | `#2563eb`            |
| Finance       | `#0f172a`            |
| Healthcare    | `#0891b2`            |
| Manufacturing | `#ea580c`            |
| Retail        | `#db2777`            |
| Energy        | `#16a34a`            |
| Default       | Nexus teal `#01696F` |
