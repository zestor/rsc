# Knowledge Management

Create and maintain support knowledge base articles. Every good KB article reduces future ticket volume.

## Article Types

### How-to

```
# How to [task]
[Overview — what and who]
## Prerequisites
## Steps
## Verify It Worked
## Common Issues
```

### Troubleshooting

```
# [Problem — what user sees]
## Symptoms
## Cause
## Solution (primary fix first, alternatives after)
## Prevention
## Still Having Issues?
```

### FAQ

```
# [Question in customer's words]
[Direct answer — 1-3 sentences]
## Details
```

### Known Issue

```
# [Known Issue]: [Brief description]
Status: [Investigating / Workaround Available / Fix In Progress / Resolved]
Affected: [Who/what]
Last updated: [Date]
## Symptoms
## Workaround
## Fix Timeline
## Updates
```

## Title Best Practices

| Good                                              | Bad               | Why                              |
| ------------------------------------------------- | ----------------- | -------------------------------- |
| "How to configure SSO with Okta"                  | "SSO Setup"       | Specific, includes the tool name |
| "Fix: Dashboard shows blank page"                 | "Dashboard Issue" | Includes the symptom             |
| "Error: 'Connection refused' when importing data" | "Import Problems" | Includes exact error message     |

## Maintenance Cadence

| Activity                                          | Frequency         |
| ------------------------------------------------- | ----------------- |
| New article peer review                           | Before publishing |
| Accuracy audit (top-traffic articles)             | Quarterly         |
| Stale content check (not updated in 6+ months)    | Monthly           |
| Known issue status updates                        | Weekly            |
| Gap analysis (top ticket topics without articles) | Quarterly         |

**Lifecycle:** Draft → Published → Needs Update → Archived → Retired

**Update existing** when steps need refreshing, a detail is missing, feedback says a section is confusing, or a better workaround was found. **Create new** when a feature needs docs, a resolved ticket reveals a gap, an article covers too many topics, or a different audience needs the same info explained differently.

## Gotchas

- **Include exact error messages in titles and body** — customers copy-paste errors into search. "Connection refused" finds articles; "import problems" doesn't.
- **Use customer language, not internal jargon** — "can't log in" not "authentication failure."
- **A wrong article is worse than no article** — outdated steps that don't work anymore generate tickets instead of deflecting them.
- **Keep known issue articles live 30 days after resolution** — customers still searching the old symptoms need to find the "resolved" status.
- **One problem per article** — if an article covers two topics, split it. Compound articles rank poorly in search and confuse readers.