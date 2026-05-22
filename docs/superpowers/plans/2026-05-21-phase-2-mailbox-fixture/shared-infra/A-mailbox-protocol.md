# Slice A — MailboxBackend protocol + helpers

> Lives in `backend/apps/stubs/_shared/auth/mailbox.py`.
> Implemented in slice 01.

## Surface

```python
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class InboundMessage:
    """One email the target sent. Body is the decoded text/plain
    or text/html part; never raw MIME."""
    to_address: str
    from_address: str
    subject: str
    body_text: str
    body_html: str
    arrived_at: datetime
    message_id: str


class MailboxBackend(Protocol):
    def wait_for_message(
        self, to_address: str, *,
        since: datetime, timeout_s: float = 30.0,
    ) -> InboundMessage | None:
        """Block up to ``timeout_s`` for the first message
        addressed to ``to_address`` whose arrival is ≥ ``since``.
        Returns None on timeout. None is a normal outcome — the
        stub maps it to a `stale` / `low-confidence` Finding."""


def load_mailbox_backend() -> MailboxBackend | None:
    """Construct the backend from env vars. Returns:

    * an `IMAPMailbox` when `FIXTURE_MAILBOX_BACKEND=imap`
    * a `MailosaurMailbox` when `...=mailosaur`
    * a `CatchallMailbox` when `...=catchall`
    * `None` when `...=none` (registration-without-email path)
    * raises `MailboxConfigError` for any other value or
      missing-required-config combination.
    """
```

## Token-extraction helpers

```python
def extract_reset_token(
    message: InboundMessage, *,
    url_substring: str = "reset",
) -> str | None:
    """Find the first URL containing ``url_substring`` in the
    message body and return its query-string token parameter
    (`token | code | t | k`, in that order). None if no link
    matched."""


def extract_link(
    message: InboundMessage, *,
    url_substring: str,
) -> str | None:
    """Return the first URL in the body that contains
    ``url_substring``. Used by stubs that need the full link
    (not just the token), e.g. reset-poisoning."""
```

## FakeMailbox (tests only)

```python
class FakeMailbox:
    """Stub fixture for tests. Pre-loaded with InboundMessage
    instances; `wait_for_message` returns them in FIFO order."""
    def __init__(self, messages: list[InboundMessage]) -> None: ...
    def append(self, msg: InboundMessage) -> None: ...
    def wait_for_message(self, to_address, *, since, timeout_s=30.0):
        ...  # picks the first matching message
```

The FakeMailbox lives in `backend/apps/stubs/_shared/auth/tests/`
NOT in production code — every real stub gets a real backend.

## Tests (slice 01)

* `wait_for_message` returns the first message matching the
  `to_address` filter.
* `since` cutoff drops messages older than the marker.
* `timeout` returns None without raising.
* `extract_reset_token` extracts from a sample reset email.
* `extract_link` returns the first matching URL.
* `load_mailbox_backend` reads env vars, returns the right type,
  raises on bad config.
* `FakeMailbox` is order-preserving + filter-respecting.

## Why a Protocol, not an ABC

The four backends share a behaviour contract (read messages
addressed to X arriving after Y). They don't share much
implementation. A Protocol gives us static type-checking without
forcing inheritance. Tests inject `FakeMailbox` — duck-typing
matches the Protocol automatically.
