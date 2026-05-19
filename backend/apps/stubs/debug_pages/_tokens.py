"""Shared secret/env token vocabulary for stub 1.10.

Single source of truth for both:
- `signals.find_env_leak_markers` (substring scan, returns leak labels)
- `redact.redact_secrets` (regex alternation, masks values)

Drift between the two shapes would silently leak secrets — if a token
appeared in the scanner's vocabulary but was missed by the redactor,
the unredacted value would reach Evidence.raw_excerpt. Keeping one
authoritative tuple eliminates that risk.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/10-debug-pages.md
"""
from __future__ import annotations


# Secret-like key names — presence alone implies a leaked credential
# regardless of the value's shape. Spec §Strong indicators env/config
# leak markers.
SECRET_KEY_TOKENS: tuple[str, ...] = (
    "secret_key",
    "api_key",
    "apikey",
    "password",
    "db_password",
    "database_url",
    "redis_url",
    "aws_access_key_id",
    "aws_secret_access_key",
    "private_key",
)

# Pure env-var indicators: keys that prove the page dumps the runtime
# environment but aren't themselves secret-shaped.
ENV_ONLY_TOKENS: tuple[str, ...] = (
    "app_env",
    "node_env",
    "debug=true",
)

# Every secret-key token is also an env var when it appears on a debug
# page. Compose explicitly so the dual-label intent is data, not
# accidental copy-paste duplication.
ENV_KEY_TOKENS: tuple[str, ...] = ENV_ONLY_TOKENS + SECRET_KEY_TOKENS
