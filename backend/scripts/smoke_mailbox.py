"""Manual smoke for the configured mailbox backend.

Operator runs this once at fixture-setup time to confirm the IMAP
credentials work. Not exercised in CI.

Usage:
    docker compose exec backend python scripts/smoke_mailbox.py

Reads FIXTURE_MAILBOX_* env vars from the container environment.
Prints the latest message addressed to the IMAP user with metadata
(subject / from / date) so the operator can verify the wiring.

Exit 0 on success (latest message found OR inbox empty); 1 on
MailboxConfigError (bad credentials, missing env var, etc.).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import django


def main() -> int:
    here = os.path.abspath(os.path.dirname(__file__))
    app_root = os.path.dirname(here)
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from apps.stubs._shared.auth.mailbox import (
        MailboxConfigError, load_mailbox_backend,
    )

    try:
        backend = load_mailbox_backend()
    except MailboxConfigError as exc:
        print(f"FAIL: {exc}")
        return 1
    if backend is None:
        print("FIXTURE_MAILBOX_BACKEND=none → backend disabled. "
              "No mailbox to smoke-test.")
        return 0

    addr = os.environ.get("FIXTURE_MAILBOX_IMAP_USER")
    if not addr:
        print("FAIL: FIXTURE_MAILBOX_IMAP_USER not set in container env.")
        return 1

    print(f"polling {addr} for the latest message in the last hour…")
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    msg = backend.wait_for_message(addr, since=since, timeout_s=5.0)
    if msg is None:
        print("OK: inbox queried successfully — no messages in the last hour.")
        print("    (configure target to send a test email, then re-run.)")
        return 0
    print("OK: latest message found")
    print(f"  from:       {msg.from_address}")
    print(f"  to:         {msg.to_address}")
    print(f"  subject:    {msg.subject}")
    print(f"  arrived_at: {msg.arrived_at.isoformat()}")
    print(f"  message_id: {msg.message_id}")
    text_preview = msg.body_text[:200].replace("\n", " ")
    print(f"  body[:200]: {text_preview!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
