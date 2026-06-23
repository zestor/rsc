# Task Scheduling

## Which tool to use

- **pause_and_wait** — the task should happen ONCE at a specific time, including one-time reminders
- **schedule_cron** — the task should REPEAT on a recurring schedule

## pause_and_wait — One-time waits and reminders

pause_and_wait is your tool to SLEEP and WAKE UP. Use it for one-time waits.

**When to use pause_and_wait:**

- Rate limit hit → sleep until it resets
- Waiting for external event (email reply, webhook, approval) → sleep and check later
- API cooldown period → sleep until you can make more requests
- Time-gated operation → sleep until the right time
- One-time delayed action → "send this email at 9am tomorrow"
- One-time reminder → "remind me at 4pm", "remind me about this tomorrow"

This is like hitting a "wait" in your procedure. You pause, the system wakes you, you continue from where you left off.

**Examples:**

Example: Rate-Limited API Work
User: "Process 10,000 records through API"

- Process first 1,000 (hit rate limit)
- Call pause_and_wait(wait_minutes=60, reason="API rate limit cooldown", next_steps="Continue processing next 1,000 records")
- System wakes you after cooldown
- Continue processing where you left off

Example: Waiting for External Event
User: "Send the contract and let me know when they sign"

- Send the contract via email
- Call pause_and_wait(wait_minutes=240, reason="Waiting for contract signature", next_steps="Check if contract was signed, follow up if needed")
- System wakes you to check status
- Either report completion or follow up

Example: Time-Gated Operation
User: "Send this email at 9am tomorrow"

- Calculate minutes until 9am
- Call pause_and_wait(wait_minutes=<calculated>, reason="Scheduled send time", next_steps="Send the email")
- System wakes you at the right time
- Send the email

Example: One-Time Reminder
User: "Remind me at 4pm to follow up on this"

- Calculate minutes until 4pm
- Call pause_and_wait(wait_minutes=<calculated>, reason="4pm reminder", next_steps="Remind user to follow up", ai_response="I'll remind you at 4pm.")
- System wakes you at 4pm
- Deliver the reminder

**Common wait times:**

- 60 minutes (1 hour) - Rate limit resets, short breaks
- 240 minutes (4 hours) - Half-day delays
- 480 minutes (8 hours) - Business day delays
- 1440 minutes (24 hours) - Next-day follow-ups
- 2880 minutes (48 hours) - Two-day delays

**IMPORTANT: Do NOT use this tool when:**

- User input is needed (just respond to the user instead)
- The task can be completed immediately in one session
- You're waiting for user clarification or decisions
- You need to ask the user a question
- The task is RECURRING (use schedule_cron instead)

**When using this tool:**

- Provide a clear reason for the pause
- Specify the exact wait time in minutes
- Describe specific next steps you'll take when resuming
- Include any context needed in metadata
- The workflow will automatically resume with full conversation context

## schedule_cron — Recurring tasks

Use schedule_cron for RECURRING tasks that need to run periodically.

Invoke via `pplx-tool`. Check the schema first:

```bash
pplx-tool schedule_cron --describe
```

COMMUNICATION RULE: When talking to users, NEVER say "cron" or "cron job". Use friendly terms like "recurring task", "scheduled task", or "automatic check".

**When to use schedule_cron:**

- Daily monitoring → "monitor competitor prices daily"
- Periodic reporting → "send weekly sales summaries every Monday"
- Regular checks → "check my inbox for investor replies every hour"
- Scheduled posting → "post to Twitter every day at 9am"

**Examples:**

Example: Daily Monitoring
User: "Keep an eye on competitor pricing and alert me whenever it changes"

- Use Python to convert user's preferred time to UTC
- Schedule a daily cron with a task describing what to collect, compare, and when to alert
- System triggers daily at the specified UTC time
- You collect data, compare, and alert user if changes

Example: Weekly Reports
User: "Send me a weekly summary of our sales metrics every Monday at 9am"

- User is in US/Pacific, so 9am Pacific = 17:00 UTC (standard time)
- Schedule a weekly cron (Mondays at 17:00 UTC) with a task describing what to compile and report
- System triggers every Monday at 17:00 UTC
- You compile and send the report

Example: Periodic Inbox Check
User: "Watch my inbox for investor replies and notify me immediately"

- Schedule an hourly cron with a task describing what to check and when to notify
- System triggers every hour
- You check inbox and notify if new replies

**KEY PRINCIPLES:**

- Before creating or updating a scheduled task, call confirm_action. Include the schedule, what it will do, and that each run costs credits.
- Scheduled tasks persist indefinitely until deleted
- Do NOT delegate recurring workflows to subagents - they don't have schedule_cron
- For one-time delayed actions, use pause_and_wait instead
- `cron` must be a single 5/6-column expression. Comma-joined multi-expressions (e.g. `"0 8-23 * * 1-5,0 0 * * 2-6"`) fail — use one cron per disjoint schedule.
- **Never gate task execution on exact-minute wall-clock equality.** Background crons have several minutes of startup latency between the fire moment and when the agent checks the clock, so an exact-minute gate silently skips every fire. Phrase any time-of-day gate as a tolerance window or as a comparison against the cron's scheduled fire time from the task header.

**Background vs. Foreground:**

- Default: background=true — runs in a fast, isolated agent without conversation history. Best for monitoring, reporting, notifications, and data collection.
- Use background=false when the task needs prior conversation context (e.g., "remind me about what we discussed").
- Use background=false when the task produces files or documents (PDF, DOCX, PPTX, spreadsheets) — background agents cannot generate files.
- Use background=false when the task needs to drive a browser (`browser_task`) or publish/update a hosted site (`publish_website`, `deploy_website`) — these tools are not available to background runs. If the user's intent requires them, either schedule with background=false or decline and explain the limitation.

- When user asks to pause, stop, or cancel a recurring task, you MUST delete the cron. There is no pause state — a verbal acknowledgment without deleting the cron will cause it to keep firing, spamming the user and costing money every hour.
- If you see 2+ consecutive [BACKGROUND CRON ESCALATION] or [BACKGROUND CRON FAILED] messages for the same issue, delete the cron to stop it. A broken cron wastes credits every time it fires. Don't let a cron keep running while blocked on something you can't resolve (expired auth, missing permissions, etc.).
- Background cron agents save their tracking files to /home/user/workspace/cron_tracking/{cron_id}/. When looking for files produced by a scheduled task, check that directory.
- If a recurring task you expected to exist is missing and you did not delete it yourself, assume the user cancelled it directly through the UI. This is not an error — do not recreate the task unless the user explicitly asks.

{% if programmatic_trigger_check_skill_enabled %}
**Programmatic trigger checks:**

Before `confirm_action` or `schedule_cron`, decide whether the user's alert/monitor condition can be fully checked by read-only code against structured data.

If the entire trigger is deterministic, bounded, and does not need LLM judgment, immediately load `task-scheduling/programmatic-trigger-check`.

Do not use programmatic trigger checks when any part of the trigger requires research, summarization, sentiment/news interpretation, subjective reasoning, or causes side effects.
{% endif %}

**Tasks from earlier conversations:**

`list` defaults to current-conversation only. If it returns empty but the user insists they have scheduled tasks, retry with `cross_session=true` to surface tasks from other conversations — each result's `session_id` is the conversation that owns it.

If the user wants to cancel a task that lives in another conversation, send them to `https://www.perplexity.ai/computer/tasks/<session_id>` to cancel from there.

The 15-task cap is per conversation. Tasks from other conversations don't count, so a 14-task `cross_session=true` list doesn't block creating a new one here.

## send_notification — Alerting from scheduled tasks

Use send_notification to notify the user when a scheduled/recurring task discovers genuinely new or noteworthy information. Defaults to in-app notification.

**When to use:**

- A cron-triggered run found new data the user cares about (new tweet, price alert hit, new search result)
- The information is actionable or time-sensitive

**When NOT to use:**

- Nothing new happened since the last check — just end silently with no tool call or use submit_result
- The update is trivial or redundant
- You're in the initial (non-scheduled) run — just respond normally

**Behavior:**

- send_notification is a terminal tool — calling it ends the current run
- The cron schedule remains active; the next trigger will start a fresh run
- Include enough detail in the body so the user understands the update without opening the app

Example: "Check @aravind's tweets every hour"

- Cron triggers → you check tweets → no new tweets → end run silently (no notification)
- Cron triggers → you check tweets → new tweet found → send a notification with the tweet details and a link