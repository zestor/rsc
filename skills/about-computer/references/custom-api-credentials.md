# Custom API Credentials

Computer supports bring-your-own-key access for third-party HTTPS APIs that do not have a built-in connector.

## How users invoke it

Natural language is enough — for example, "I have credentials for the ___ API."

## Secure credential entry

Computer opens an in-thread credential form for the user; users enter the key there, not into chat. Computer should never ask users to paste secrets into the conversation, and never echo credential values back.

## Scope and lifetime

Custom API credentials are scoped to the current thread only — not shared across conversations or with other users.

## How credentials are used

After submission, Computer can call the matching service host over HTTPS; the credential is injected automatically through a secure proxy. Computer does not see the raw credential value after creation.

## Managing credentials

Users can view and revoke saved credentials at any time from the in-app credentials pane.

## Prefer built-in connectors

If Computer has a built-in connector for the service, use that first. Managed connectors are richer and usually support more structured read/write actions than a raw API key.
