# Slice D — Self-hosted catch-all on h1.cocode.dk

> Lives in `backend/apps/stubs/_shared/auth/_catchall.py` (Python
> client) + `infra/mailsink/` (Postfix + FastAPI shim) on h1.
> Operator-action setup; spec'd here as the long-term zero-cost
> option.

## Architecture

```
target sends email to  scanner-fixture-1@scanner-fixture.cocode.dk
                              ↓ MX record
                       h1.cocode.dk:25  ←  Postfix accepts mail
                              ↓ pipe to virtual_alias_maps
                       /opt/mailsink/inbox/<recipient>/<msg-id>.eml
                              ↓ FastAPI shim reads
                       GET /mailsink/messages?to=...&since=...
                              ↓ JSON response
                       CatchallMailbox client in Python
```

## DNS setup (operator-action)

1. MX record: `scanner-fixture.cocode.dk → h1.cocode.dk` priority 10.
2. SPF record on `scanner-fixture.cocode.dk` permitting h1's IP
   (otherwise spam filters at large providers may reject our
   outbound — though we don't send, some providers reject mail
   addressed to a domain with no SPF as a sanity check).
3. Wildcard A: `*.scanner-fixture.cocode.dk → 178.105.140.53`
   (so any aliased sub-address resolves; optional for catchall
   itself but useful for OAuth redirect-URI tests).

## Postfix config (operator-action)

* `main.cf`: `mydestination = scanner-fixture.cocode.dk`,
  `virtual_alias_domains = scanner-fixture.cocode.dk`,
  `virtual_alias_maps = pcre:/etc/postfix/virtual.pcre`.
* `/etc/postfix/virtual.pcre`:
  `/^(.+)@scanner-fixture\.cocode\.dk$/  mailsink+$1`
* `mailsink` user pipes incoming mail to `/opt/mailsink/spool/`
  via `procmail` or a tiny custom pipe-script that writes one
  `.eml` per message into `<spool>/<recipient>/<timestamp>.eml`.

## FastAPI shim (operator-action)

* `/mailsink/messages?to=<addr>&since=<iso>` returns JSON: list
  of `{message_id, from, subject, body_text, body_html,
  arrived_at}` sorted oldest-first.
* `/mailsink/messages/<message_id>` returns the full parsed
  message.
* Auth: `Authorization: Bearer <token>` header. Token rotates
  on operator action; stored in `FIXTURE_MAILBOX_CATCHALL_TOKEN`.
* Single binary deployment, ~150 lines of Python on h1.

## Client surface (Python in this repo)

```python
class CatchallMailbox:
    def __init__(self, *, base_url: str, token: str) -> None: ...
    def wait_for_message(self, to_address, *, since, timeout_s=30.0):
        """Poll `GET /mailsink/messages` every 1 s for up to
        ``timeout_s``. Return the first match."""
```

## Tests

* HTTPx-mocked against a stand-in FastAPI response.
* Bearer-token header sent.
* Polling: empty response repeats up to timeout.
* Match: first message with `to == to_address` AND
  `arrived_at >= since` wins.
* Non-200 raises `MailboxConfigError` with the body excerpt.

## Why this is worth building

* Zero recurring cost. Already-paid hosting on h1.
* No external dependency. If Mailosaur changes their API or
  Gmail revokes the app password, the scanner keeps working.
* OAuth redirect-URI tests (stub 2.14) can register
  `https://scanner-fixture.cocode.dk/oauth/cb` and observe the
  callback hit the same FastAPI shim with a different route. One
  fixture covers two concerns.

## When to defer

If the operator just wants to validate Phase 2 stubs against
DVWA / Juice Shop / WebGoat (which all support `localhost`-ish
test emails), start with `imap` or `mailosaur` and defer the
self-hosted catchall to Phase 3.
