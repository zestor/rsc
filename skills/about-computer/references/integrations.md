# External Integrations

Computer connects to 400+ external services through a managed connector framework.

## How it works

- Users authenticate once via OAuth. Computer uses tokens securely.
- Available connectors are discovered dynamically — Computer checks what's connected before saying it can't access something.
- Connectors support both reading and writing — not just fetching data but taking actions.

## Supported services (examples)

| Category           | Services                                              |
| ------------------ | ----------------------------------------------------- |
| Communication      | Slack, Gmail, Outlook, Microsoft Teams                |
| Calendar           | Google Calendar, Outlook Calendar                     |
| Documents          | Notion, Google Docs, Google Sheets, Dropbox, OneDrive |
| Project management | Linear, Jira, Asana, Trello                           |
| CRM                | HubSpot, Salesforce                                   |
| Development        | GitHub, GitLab                                        |
| Data               | Airtable, Google Sheets, databases                    |
| Lifestyle          | Spotify, Strava                                       |
| And more           | Hundreds of additional connectors across categories   |

## What Computer can do with integrations

- **Read**: Search emails, pull calendar events, query CRM records, fetch documents, list tasks.
- **Write**: Send messages, create tasks, update records, post to channels, send emails, create calendar events.
- **Search**: Find specific items across connected services — emails matching a query, documents mentioning a topic, tasks assigned to someone.
- **Analyze**: Combine data from multiple services, summarize and visualize key patterns, and generate actionable insights or recommendations from emails, docs, metrics, and tickets.

## Connecting a new service

If the user needs a service that isn't connected yet, Computer provides an OAuth link. The user clicks it, authorizes access, and the connector becomes available immediately.

## Example use cases

- Pull today's calendar and prep for each meeting using CRM data.
- Search Slack for messages about a topic and summarize the discussion.
- Create Jira tickets from a list of requirements.
- Send a personalized email to each contact in a CRM pipeline stage.
- Pull metrics from Google Sheets and generate a report.
