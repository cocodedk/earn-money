# Slice C — MailosaurMailbox backend

> Lives in `backend/apps/stubs/_shared/auth/_mailosaur.py`.
> Optional. Built only if the operator subscribes to Mailosaur.
> Spec'd here for symmetry with the IMAP backend.

## Why Mailosaur

* Per-test inboxes, no setup. `mailbox.create_inbox()` returns a
  fresh `xxxxxx@SERVERID.mailosaur.net` address.
* Sub-second delivery vs 5-30 s for IMAP.
* Designed for automated testing. No bot-detection. No rate
  limits on the polling endpoint.
* REST API → small implementation surface, mockable.

## Surface

```python
class MailosaurMailbox:
    def __init__(
        self, *, api_key: str, server_id: str,
        base_url: str = "https://mailosaur.com/api",
    ) -> None: ...

    def create_inbox(self) -> str:
        """Return a fresh `xxxxxx@<SERVER>.mailosaur.net` address.
        Per-probe alias — the inbox is unique to this scan run."""

    def wait_for_message(self, to_address, *, since, timeout_s=30.0):
        """Poll the Mailosaur `/messages/await` endpoint with the
        sentTo / receivedAfter parameters Mailosaur natively
        supports. Returns InboundMessage on success, None on
        timeout."""
```

## API mapping

* Mailosaur's `POST /messages/await` accepts a JSON body with
  `sentTo`, `receivedAfter`, `timeout` — maps 1:1 to the
  Protocol's signature.
* The Mailosaur response includes parsed body text + HTML +
  links + attachments. We use the `text.body` field for
  `body_text` and `html.body` for `body_html`.
* Auth: `Authorization: Bearer <api_key>` header.

## Inbox lifecycle

* Per-scan-run inboxes via `create_inbox()`. The scan-run ID is
  embedded in the inbox name so concurrent scans don't collide.
* Mailosaur auto-deletes after 24 h. No cleanup code needed.

## Tests

* HTTPx-mocked: a fake Mailosaur API endpoint returns scripted
  responses.
* Bearer-token header presence.
* `receivedAfter` is ISO-8601-formatted from the `since` arg.
* Timeout returns None without raising on httpx-side timeout.
* 401 from the API raises `MailboxConfigError` (operator should
  see "bad API key", not a generic network error).

## Cost note

Mailosaur free tier is 10 messages/day — fine for development,
not for a multi-stub-per-day scan cadence. Paid tier is $9/mo
for 1000 messages.
