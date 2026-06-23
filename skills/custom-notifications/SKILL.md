# Custom Notifications

## Channel selection

`send_notification` supports three channels:

- **`in_app`** (default) — always use this unless the user asks for something else.
- **`push`** — only when the user explicitly asks for phone/mobile alerts.
- **`email`** — only when the user explicitly asks for email delivery (e.g., "email me a daily summary").

Never add `push` or `email` without explicit user request for these channels. If the user asks to "notify me", use `in_app`.

## Email templates

When using `channels=["email"]`, set `email_args` to a typed payload. The discriminator is `template`; each variant declares its own fields.

- **`generic`** — General-purpose email; renders the notification body as formatted HTML. Use when no specialized template fits.
  - Fields: `template: "generic"`, `subject?: str` (defaults to the notification title)
- **`finance_digest`** — Personal-finance email with structured overview metrics on top and structured body sections below. Use whenever the email is primarily about the user's holdings, net worth, or portfolio movement, regardless of cadence (scheduled or one-off).
  - Before composing the call, **load `custom-notifications/finance-digest`** for content rules, title guidance, and a full example.

For simple emails, use `email_args={"template": "generic"}`.

## Gotchas

- Do NOT use citations or claim links in the notification body or `email_args` content. No `[text](claim:N)` links.
- Section/item values support markdown — use it for rich text like lists or tables. For simple values like numbers or percentages, use plain text.
- Do NOT notify just to say "nothing happened" or "no updates found". End the run silently instead.
- Set `schedule_description` for recurring tasks so the user sees the cadence (e.g., "Daily · 9am").
- Push body is truncated to a short preview — put the full details in `body` for in-app/email, not in `title`.
- `send_notification` is terminal — calling it ends the current run. The cron schedule stays active.
- Do NOT use `confirm_action` before sending notifications. The user already consented when they set up the task. Just send it.