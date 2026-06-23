# Custom Credentials

Custom credentials let the user bring their own API key for a third-party HTTPS service that has no built-in connector. They are scoped to **this thread only** — not shared across conversations.

## Three tools, one decision

All three are dispatched via `pplx-tool`. Run `pplx-tool <tool> --describe` once per tool to fetch the schema before first use.

- `pplx-tool list_credentials` — read the current set. Call this first whenever you're unsure what's already saved.
- `pplx-tool request_credential` — open an in-thread form for the user to add a credential. Only call this after `list_credentials` confirmed nothing matches the host you need.
- `pplx-tool revoke_credential` — soft-delete a saved credential. Only on explicit user request; the tool shows its own confirmation gate.

## Using a saved credential from `bash`

Pass `api_credentials=['custom-cred:<host>']` on the `bash` call that issues the request. Auth is injected automatically through an HTTPS proxy — never paste the credential value into the command.

Use `curl`, Python `requests`, `httpx` (sync or `httpx.AsyncClient`), `urllib`, or vendor SDKs that delegate to those — they all read `HTTPS_PROXY` and pick up the injected auth automatically. **Don't use `aiohttp`** — it ignores `HTTPS_PROXY` by default and the request goes out unauthenticated. For async work, prefer `httpx.AsyncClient`.

Footguns:

- **Non-HTTPS protocols are not intercepted** — websockets, raw TCP, gRPC over h2c. `api_credentials` won't help; the request goes out unauthenticated.
- **SDKs that pin their own HTTP transport** can bypass the proxy. If a request mysteriously 401s with `api_credentials` set, fall back to `httpx`/`requests` directly.

## Using a saved credential from website backends

For `start_server`, pass `api_credentials=['custom-cred:<host>']` using the returned `host`. For `publish_website`, pass `credentials={'custom-cred:<host>': ''}`. Use the exact `website_url_env_var` and `website_token_env_var` names returned by `list_credentials`; the backend should call the URL env var and send the token env var as `x-api-key`.

## Filling out `request_credential`

- **`host`** — hostname only. No scheme, no path, no port unless the service requires one. `api.openweathermap.org`, not `https://api.openweathermap.org/data/2.5/`.
- **`credential_type`** — pick the closest fit:
  - `BearerCred` for `Authorization: Bearer <token>`
  - `HeaderCred` for a single named header (e.g. `X-API-Key: <key>`)
  - `BasicCred` for username + password
  - `QueryParamCred` for `?api_key=<key>` query strings
  - `HeadersCred` for multi-header schemes
- **`auth_param_name`** — for `HeaderCred` and `QueryParamCred`, prefill the exact key name (e.g. `X-API-Key`, `api_key`) when you're confident from public API docs. Leave unset when unsure, or for `BearerCred`/`BasicCred` where it doesn't apply.
- **`reason`** — one short sentence saying what you'll do with the credential for the user's current task. Don't restate the service or credential type (the form already shows them).

## Stale state from in-UI changes

The user can add or revoke credentials directly in the credentials pane without telling you. So:

- Re-run `pplx-tool list_credentials` before relying on results from earlier in the conversation.
- Definitely re-list before retrying a request that just 401'd — the credential may have been revoked.
- If the user says "I already added it," list first instead of re-prompting with `request_credential`.

## Privacy

`list_credentials` returns metadata and safe usage hints only; it never returns the secret. Don't ask the user to paste raw credential values into chat — direct them to the form opened by `request_credential`, or to the credentials pane.