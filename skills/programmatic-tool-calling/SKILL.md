# Programmatic Tool Calling

The `external-tool` CLI lets code running in the sandbox call the user's connected external tools directly. **Credential preset:** `external-tools`.

## When to Use Code Instead of `call_external_tool`

**Default to writing code** when a task involves external tools and any of:

- **Bulk operations** — processing many items (emails, messages, records). Code keeps the data in the sandbox instead of flowing thousands of results through your context window.
- **Filtering and transforming** — searching 500 emails to find 3 that match? Do it in code. Don't page through results via sequential tool calls.
- **Parallel calls** — sending the same message to 10 channels, fetching from multiple connectors at once.
- **Ongoing use** — websites, cron jobs, or any code that will call tools repeatedly.

Use `call_external_tool` directly only for simple one-off calls where the result is small and you need to reason about it immediately.

## Step 0: Discover and Experiment

Use your regular tool-calling interface to discover what's available **before** writing code.

1. Call `list_external_tools` to see connected tools and their schemas
2. Call `describe_external_tools` to get the full input schema for tools you plan to use — `call_external_tool` will error if you skip this
3. Call `call_external_tool` with a test input to see the actual response shape
4. **Pay attention to the `structure` field in the response** — it tells you the type and shape of the result (e.g., "JSON string (65248 chars)" means the content is a JSON-encoded string you'll need to `json.loads()`, not a dict). Output schemas vary by connector and some return nested JSON strings. The test response is your source of truth.

Only after you understand the input/output format should you write code that uses the CLI.

## Tools That Require `call_external_tool`

Some tools need workspace file resolution that only `call_external_tool` provides. **Do NOT use the `external-tool` CLI for these** — it will fail because the CLI cannot upload workspace files to S3.

| Tool           | Affected source_ids                          | Why                                                         |
| -------------- | -------------------------------------------- | ----------------------------------------------------------- |
| `export_files` | `google_drive`, `onedrive`, `dropbox`, `box` | Requires `file_paths` → presigned S3 `file_urls` resolution |

For these tools, use `call_external_tool` directly instead of writing code with the CLI.

## CLI Usage

```
external-tool call '{"source_id": "...", "tool_name": "...", "arguments": {...}}'
```

Output is JSON on stdout. Errors are JSON on stderr with a non-zero exit code:

```json
{"error": "auth_required", "auth_url": "https://...", "source_id": "gmail"}
{"error": "Rate limited", "source_id": "slack", "tool_name": "slack__send_message"}
```

**Python helper** (async — works in both scripts and servers):

```python
import asyncio, json

async def call_tool(source_id, tool_name, arguments):
    proc = await asyncio.create_subprocess_exec(
        "external-tool", "call", json.dumps({
            "source_id": source_id, "tool_name": tool_name, "arguments": arguments,
        }),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode())
    return json.loads(stdout.decode())
```

**Node helper:**

```javascript
const { execSync } = require('child_process');
function callTool(sourceId, toolName, args) {
  const params = JSON.stringify({ source_id: sourceId, tool_name: toolName, arguments: args });
  return JSON.parse(execSync(`external-tool call '${params}'`).toString());
}
```

## Pattern: Process in Code, Return a Summary

Write scripts that fetch, filter, and chain data across services in the sandbox, then return only what you need. Data stays in the execution environment — your context sees a compact summary instead of thousands of raw API objects. You can do arbitrarily complex things in code: paginate through history, aggregate across multiple connectors, sync data between services, filter and transform results — anything you can write in Python or Node.

## Parallel Execution

Use a loop instead of sequential `call_external_tool` calls. Pass `api_credentials=["external-tools"]` on the bash call.

```python
channels = ["#engineering", "#product", "#design"]
for ch in channels:
    call_tool("slack", "slack__send_message", {"channel": ch, "text": "Weekly update"})
```

Examples:

- Scan 1000 Slack messages across 20 channels, run sentiment analysis with pandas, post a summary to Notion
- Pull all GitHub issues, cross-reference with Jira tickets, generate a reconciliation report as a CSV
- Fetch Google Calendar events for the week, enrich each with attendee info from the CRM, build an HTML briefing doc

## Websites

**Load the `website-building` skill** before building a website that uses external tools. It covers backend servers, deployment, and port forwarding.

Write a backend server that calls `external-tool` from its endpoints. Start it with `api_credentials=["external-tools"]` — the token lasts 10 minutes, long enough for local testing. After deployment, the token is also refreshed on every incoming frontend request through the site proxy.

- **Do NOT call external tools from frontend JavaScript.** The credentials are server-side only. Always go through a backend server.

Examples:

- Email dashboard that searches Gmail, clusters threads by topic with sklearn, and renders an interactive React UI
- Meeting prep app that pulls Google Calendar events, fetches related Notion docs and Slack threads, and generates a briefing page
- CRM search tool that queries Salesforce leads, joins with Google Sheets data, and displays filterable results with charts

## Cron Jobs

Write and test the script yourself first, then hand it off to a cron subagent. Instruct the cron subagent to use `api_credentials=["external-tools"]` on its bash calls — you should also use that field when testing.

Examples:

- Daily digest that scans unread emails, Slack mentions, and Notion updates overnight, then posts a morning summary to Slack
- Weekly pipeline report that pulls deal data from Salesforce, computes conversion metrics, and creates a formatted Google Doc
- Monitoring script that checks GitHub CI status every hour, pages through recent failures, and opens Jira tickets for flaky tests

## Credential Lifetime

The token lasts **10 minutes** and is refreshed automatically:

| Context        | Refresh trigger                                         |
| -------------- | ------------------------------------------------------- |
| Bash calls     | Each `bash()` with `api_credentials=["external-tools"]` |
| Websites       | Every incoming HTTP request from the frontend           |
| Cron subagents | Each `bash()` with `api_credentials=["external-tools"]` |

## Error Handling

- **Rate limits.** If you hit rate limits, back off with increasing delays before retrying.
- **Auth required.** If a tool returns `auth_required`, the user needs to reconnect that service. Surface the error rather than retrying.