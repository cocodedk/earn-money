# Slice 04 — Self-hosted catchall on h1 (operator-action)

> Optional. Defer until IMAP rate limits become a problem OR you
> want OAuth-redirect-URI tests against a host we control.

## Operator-action steps (none of this is in code)

### 1. DNS

Add records on `cocode.dk` zone:
* `MX  scanner-fixture.cocode.dk.  10  h1.cocode.dk.`
* `A   scanner-fixture.cocode.dk.       178.105.140.53`
* `A   *.scanner-fixture.cocode.dk.     178.105.140.53` (wildcard
  for OAuth fixture aliases — optional).
* `TXT scanner-fixture.cocode.dk.  "v=spf1 ip4:178.105.140.53 -all"`

### 2. Postfix on h1

```bash
ssh recon-vps
apt install postfix
# Choose "Internet site" at the prompt; mail name: cocode.dk
```

Edit `/etc/postfix/main.cf`:
* `mydestination = h1.cocode.dk, localhost`
* `virtual_alias_domains = scanner-fixture.cocode.dk`
* `virtual_alias_maps = pcre:/etc/postfix/scanner-fixture.pcre`

Create `/etc/postfix/scanner-fixture.pcre`:
```
/^(.+)@scanner-fixture\.cocode\.dk$/  mailsink+$1
```

Create the `mailsink` system user with a procmail pipe that
writes each message into `/opt/mailsink/spool/<recipient>/<ts>.eml`.

`systemctl reload postfix`.

### 3. Verify

From your laptop: `swaks --to test@scanner-fixture.cocode.dk
--from anyone@example.com --server h1.cocode.dk`. The file
should appear under `/opt/mailsink/spool/test/`.

### 4. FastAPI shim

Deploy a 150-line FastAPI service on h1:
* `GET /mailsink/messages?to=<addr>&since=<iso>` — list
  matching files, parse via `email` module, return JSON.
* `GET /mailsink/messages/<id>` — full single message.
* `Authorization: Bearer <token>` required.
* `systemd` unit at `/etc/systemd/system/mailsink.service`.
* Caddy block on h1:
  ```
  h1.cocode.dk {
      reverse_proxy /mailsink/* 127.0.0.1:8090
      reverse_proxy 127.0.0.1:8080  # existing v2 stack
  }
  ```

### 5. Scanner-side wiring

```bash
# in backend/.env
FIXTURE_MAILBOX_BACKEND=catchall
FIXTURE_MAILBOX_CATCHALL_URL=https://h1.cocode.dk/mailsink
FIXTURE_MAILBOX_CATCHALL_TOKEN=<random token, also stored on h1>
```

The `CatchallMailbox` implementation in `_shared/auth/_catchall.py`
ships in a follow-up code slice.

### 6. Cleanup hygiene

* Cron on h1 deletes `/opt/mailsink/spool/*` older than 7 days.
* `mailsink+<recipient>` syntax means per-recipient subdirs; no
  cross-pollution.
* Logrotate on postfix logs.

## Why this is a separate slice

Steps 1-4 are pure operator-action work — DNS records, server
config, manual verification. Nothing in the scanner repo
changes. The Python-side `CatchallMailbox` is a tiny class once
the infra is up (~50 LoC).

## Commit (only the Python side)

`feat(stubs): CatchallMailbox backend (self-hosted mailsink)`
