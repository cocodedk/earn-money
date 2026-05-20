"""Secret-redaction for stub 1.10 evidence snippets.

Spec §Safety: "Redact snippets before persistence" — API keys,
bearer tokens, passwords, db URLs, cloud credentials. The runner
fetches raw bodies in-memory for classification but only persists
a redacted excerpt to `Evidence.raw_excerpt`, so the secret
material never reaches disk.

Redaction patterns:
- `KEY=value` env-var dump shape (case-insensitive key match)
- `"key":"value"` JSON shape
- bare `AKIA[A-Z0-9]{16}` AWS access key IDs (recognisable without
  a surrounding `KEY=` context)

The replacement marker is a constant so the output is deterministic
and idempotent — running `redact_secrets` on already-redacted text
yields the same string.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/10-debug-pages.md
"""
from __future__ import annotations

import re

from ._tokens import SECRET_KEY_TOKENS


REDACTION_MARK = "<REDACTED>"


# Derive the regex alternation from the single source of truth so a
# new token added to `_tokens.SECRET_KEY_TOKENS` automatically flows
# into the redactor — drift would silently leak the new secret class
# to Evidence.raw_excerpt.
_SECRET_KEY_ALT = "(?:" + "|".join(
    re.escape(token) for token in SECRET_KEY_TOKENS
) + ")"


# `KEY=value` shape — env-var dumps from /actuator/env, phpinfo,
# Werkzeug debugger, etc. Value runs to end of token (\S+) so the
# whole value is masked including any URL, JWT, or hex blob.
_ENV_ASSIGN_RE = re.compile(
    rf"({_SECRET_KEY_ALT})(\s*=\s*)(\S+)", re.IGNORECASE,
)

# `"key": "value"` shape — JSON dumps. Captures the opening quote
# segment + value separately so the surrounding structure stays
# intact and only the value is masked.
_JSON_ASSIGN_RE = re.compile(
    rf'("\s*{_SECRET_KEY_ALT}\s*"\s*:\s*")([^"]*)(")', re.IGNORECASE,
)

# AWS access-key ID format per the IAM key spec: 20-char identifier
# starting with `AKIA` (also `ASIA` for STS, `AGPA` for groups, etc.,
# but `AKIA` is the canonical access key form). The 16-char body is
# uppercase alphanumeric.
_AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[A-Z0-9]{16}\b")


def redact_secrets(snippet: str) -> str:
    """Return `snippet` with secret-like values replaced by
    `<REDACTED>`. Idempotent — re-running on already-redacted text
    yields the same string."""
    if not snippet:
        return snippet
    out = _ENV_ASSIGN_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{REDACTION_MARK}", snippet,
    )
    out = _JSON_ASSIGN_RE.sub(
        lambda m: f"{m.group(1)}{REDACTION_MARK}{m.group(3)}", out,
    )
    out = _AWS_ACCESS_KEY_RE.sub(REDACTION_MARK, out)
    return out
