# Website Publishing

Publish a website to a permanent `*.pplx.app` URL. The parent `website-building` skill is loaded automatically.

{% if website_publishing_permissioned %}
This session supports permissioned published-site access. The published URL uses
the app asset's Share settings, so private, org-shared, and specific-people
apps can be published without first making the asset public.

After `publish_website` succeeds, use its live visibility output in the final answer:

- Tell the user the current Visibility setting from `visibility_setting`.
- Tell the user they can update it from the Publish dropdown's Visibility
  section, and include the `visibility_settings_url` permalink.
{% else %}
Published sites in this session are public-by-URL. `publish_website` can run
regardless of the app asset's Share setting.
{% endif %}

If you are a subagent (`website_building`, cron, or any non-main agent), you cannot call `publish_website` directly — it is restricted to the main agent because publishing requires user approval that only routes to the main thread. Finish your build and `deploy_website` work and hand control back to the main agent with the project path.

---

## When to Publish

**Default to `deploy_website` for all sites.** Every site starts as a preview. Only use `publish_website` when the user explicitly asks.

Use `publish_website` when the user says things like:
- "publish this" / "make this live" / "deploy for real"
- "give me a real URL" / "a permanent link" / "a shareable link"
- "put this on pplx.app" / "give me a custom subdomain"
- "I want to share this with people"

**Do not use `publish_website` unprompted.** If the site looks ready and you think the user might want to publish, suggest it: *"This is looking great — want me to publish it to a pplx.app URL?"* But wait for confirmation.

**After editing a published site**, do not re-publish automatically. Suggest it: *"I've updated the site. Want me to re-publish to update the live version?"* Previews via `deploy_website` can be re-deployed freely without asking.

If you remember a site as published but the latest `deploy_website` result no longer includes `site_id` and `app_slug`, treat that as a signal that the user manually unpublished the site outside the agent loop. Do **not** call `publish_website` from stale memory or from the `PUBLISHED SITES` summary. Only publish again if the user explicitly asks to publish or confirms they want the live `*.pplx.app` URL restored.

---

## Unpublishing or Taking Down a Site

Agents cannot directly unpublish or delete a `*.pplx.app` site. If the user asks to unpublish, take down, delete, hide, make private, or restrict a published site:

- Do **not** use `publish_website` to replace the live site with a blank page, placeholder, redirect, or "offline" page. That is not a real unpublish and creates confusing asset/history state.
- Direct the user to use the Unpublish button in the app preview UI for that site.
{% if website_publishing_permissioned %}
- If the user wants employee-only or private access, changing the app asset's Share settings is the supported way to make the published URL private, org-shared, or visible to specific people.
{% else %}
- If the user wants employee-only or private access, explain that published `*.pplx.app` URLs are public-link sites. Recommend unpublishing and sharing the private Perplexity preview instead.
{% endif %}
- Keep the project files unchanged so the user can republish later if they want.

Suggested response:

> I can't unpublish this directly from the tool. Please open the app preview card and use the Unpublish button in the preview UI. I won't replace the site with placeholder content; once it is unpublished, the project files remain available here if you want to republish later.

---

## How It Works

- Published sites live at `https://<subdomain>.pplx.app`
- Served by Perplexity from a secure, isolated sandbox — not inside an iframe
- Each published site gets its own sandbox that auto-pauses when idle and resumes on the next request
- Static files (HTML, CSS, JS, images) are uploaded to S3 and served directly — only API/backend requests route to the sandbox
{% if website_publishing_permissioned %}
- Published sites in this session use the app asset's Share settings.
- After `publish_website`, include `visibility_setting` and the
  `visibility_settings_url` permalink in the final answer.
{% else %}
- Published sites in this session are public-by-URL.
{% endif %}
- **The same code works for both preview and publish** — no changes needed to routing, storage, paths, or links. The published version simply runs outside the iframe, which lifts browser restrictions

Users who want to host elsewhere can deploy the site via MCP or download the project files.

---

## How to Publish

**`publish_website` must be preceded by a `deploy_website` call with `project_path` equal to this tool's `dist_path`.** Both tools share a single asset chain keyed on `dist_path`, so a missing deploy_website means the frontend asset won't update (and the tool will now raise an error).

### First publish

```
deploy_website(
  user_description="Deploying My App preview",
  project_path="/home/user/workspace/project-name/dist/public",
  site_name="My App",
  entry_point="index.html",
)

publish_website(
  user_description="Publishing My App to pplx.app",
  project_path="/home/user/workspace/project-name",
  dist_path="/home/user/workspace/project-name/dist/public",
  run_command="NODE_ENV=production node dist/index.cjs",
  install_command="npm ci --omit=dev",
  port=5000,
  app_name="My App",
  subdomain="my-app"
)
```

- `user_description` — shown in the user's timeline. Always provide first.
- `dist_path` — the built static output directory (e.g. Vite's `dist/public`). These files are uploaded to S3.
- `run_command` — starts the backend server for API routes. Static files are served from S3, not from this server. Omit for fully static sites with no backend.
- `install_command` — installs production dependencies before starting the server (e.g. `npm ci --omit=dev`). Omit if the app has no runtime dependencies.
- `subdomain` — suggested subdomain (e.g. `my-app` for `my-app.pplx.app`). The user will confirm or change this before deploying. If omitted, one is generated from `app_name`.

The user sees a subdomain picker UI where they confirm or change the subdomain. After approval, the tool uploads static files, tarballs the project, and deploys.

The output includes `site_id` and `url`. **Save `site_id`** — you need it for updates.

### Updating a published site

Always call `deploy_website` first with the same `dist_path`. Only pass `site_id` to `publish_website` when the latest `deploy_website` output still includes that active `site_id`/`app_slug`. If the latest deploy output does not include published-site metadata, the site may have been manually unpublished; keep the preview only and ask before publishing again.

```
deploy_website(
  user_description="Refreshing My App preview",
  project_path="/home/user/workspace/project-name/dist/public",
  site_name="My App",
  entry_point="index.html",
)

publish_website(
  user_description="Updating My App",
  project_path="/home/user/workspace/project-name",
  dist_path="/home/user/workspace/project-name/dist/public",
  run_command="NODE_ENV=production node dist/index.cjs",
  install_command="npm ci --omit=dev",
  port=5000,
  app_name="My App",
  site_id="<site_id from previous publish>"
)
```

### Local data persistence

If the app uses SQLite, the database file **must be named `data.db` in the project root** (this is the default in the webapp template). On redeployment, `publish_website` automatically snapshots `data.db` from the old sandbox and restores it in the new one. Data in other database files or non-standard paths will not be persisted.

Before publishing a site that stores user-created data in SQLite, an in-memory database, an array/map, or any other database/file on the local filesystem, you **must** disclose the persistence limitation in the next user-facing message before calling `publish_website`. Do not skip this disclosure because the user already approved other publish warnings. Keep the wording plain and do not explain sandbox crash, kill, restart, or redeploy mechanics.

Suggested wording:

> One note before I publish: this app uses a built-in database for submitted data. That's fine for a prototype, but it isn't production-grade persistence. For durable production data, I recommend connecting Supabase or deploying on Vercel with managed storage.

### Supabase for multi-user apps

For apps needing a persistent database that works across multiple users and survives independently of the sandbox, use Supabase instead of SQLite. Supabase provides **database support only** — authentication features are not supported in published websites. Load the webapp skill and read `references/supabase.md` for setup instructions.

When publishing a Supabase app, pass credentials through the `credentials` parameter so they are proxied securely instead of stored in the sandbox:

```
publish_website(
  ...,
  credentials={"SUPABASE_URL": "https://<ref>.supabase.co", "SUPABASE_ANON_KEY": "<anon-key>"}
)
```

In the published environment, Supabase credentials are stripped from `.env` and injected as sandbox env vars routed through the agent proxy.

### Debugging a deployed API route

The webapp template's `queryClient.ts` bakes in a `__PORT_5000__` sentinel that `publish_website` (and `deploy_website`) rewrite to `port/5000` **during S3 upload** — the local `dist/public/` build output intentionally keeps the literal sentinel. Do not grep the local build to verify substitution; it will always look unreplaced. If a deployed API call fails, test the live URL directly (`curl https://<subdomain>.pplx.app/port/5000/api/...`) — don't assume the sentinel wasn't rewritten and patch around it.

---

## Security Restrictions

**LLM API access does not work in published websites.** The `api_credentials` preset (`llm-api:website`) and the credential proxy are only available in the development sandbox, not in the production sandbox that published sites run in. Sites that use LLM chat, image generation, video generation, audio generation, or transcription via `api_credentials=["llm-api:website"]` will fail after publishing.

**External tool connectors do not work in published websites.** The `call_external_tool` tool bridge is not available in the production sandbox. Sites that invoke external connectors at runtime will fail after publishing.

The published sandbox runs in an isolated environment without access to the credential proxy or tool bridge. These features are only available during development.

**Session cookies must use the `__Host-` prefix.** The proxy strips any request cookie whose name doesn't start with `__Host-` to prevent cross-tenant leakage between `*.pplx.app` sites. Default framework cookie names (`connect.sid`, `sessionid`, `session`, `_session_id`) silently stop working — configure the name explicitly, e.g. `express-session({ name: "__Host-sid", cookie: { secure: true, path: "/" } })`.

### Before publishing, check for incompatible features

Scan the project for any of the following patterns:

- `api_credentials` or `llm-api:website` in `start_server` calls
- Imports of `anthropic` or `openai` SDKs in backend server code
- Imports of `generate_image`, `generate_video`, `generate_audio`, or `transcribe_audio` helper scripts
- `call_external_tool` or external tool connector references in runtime code

If found, **try to refactor the code** to remove the dependency. For example:
- Replace LLM-generated content with pre-generated static content baked in at build time
- Move API calls to a build step that runs before publishing, caching results as static data
- Replace dynamic AI features with static alternatives

If the dependency cannot be removed (e.g. the core feature requires real-time LLM calls), explain to the user that these features will not work in the published version and let them decide:
- Publish anyway with the affected features broken/degraded
- Keep the site as a preview via `deploy_website` where everything works

---

## Pre-Publish Security Review

Before calling `publish_website`, run a security review subagent (`run_subagent`) using `security_subagent_prompt.md` from this directory as the prompt. Use `model="claude_sonnet_4_6"` — the checks are mostly grep/bash so a cheaper model is sufficient. Provide the subagent with:

- `{{project_path}}` — the absolute path to the project directory
- `{{context}}` — a brief summary of what the user is building, its purpose, and intended audience (e.g. "Personal portfolio site, public, no user data" or "Multi-user task manager with Supabase DB, intended for small teams"). This helps the subagent calibrate severity.

Based on the subagent's report:

- **BLOCK findings** (e.g. exposed secrets, credential leaks): attempt to fix them automatically (remove hardcoded keys, move secrets to env vars, etc.). If the fix requires user input or cannot be automated, present the findings and let the user decide how to proceed.
- **WARN findings**: present them to the user and let them decide whether to proceed.

---

## Limits

- 500 MB max project size (tarball)
- One subdomain per publish — reuse via `site_id` for updates