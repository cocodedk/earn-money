"""Secret/PII redactor for stub 1.17 FU-1.

Spec §Safety + §config `redact_secrets=true`: response bodies and
matched indicator snippets must be scrubbed of tokens, keys,
credentials, and PII before persistence. The redactor walks a
short pattern table and replaces each match with
`[REDACTED:<kind>]` so the kind survives for downstream debugging
without the secret value.

Patterns covered:
* `jwt` — three-segment base64url JWTs starting `eyJ`
* `bearer` — `Bearer <token>` (HTTP auth header value)
* `api_key` — well-known provider prefixes (Stripe sk_/pk_, GitHub
  ghp_/ghs_/gho_/github_pat_, AWS AKIA/ASIA, GCP GOCSPX-, Slack
  xox[baprs]-)
* `email` — RFC-5322 lite local@domain shape
* `url_creds` — `https://user:pass@host/...`
* `secret` — generic `password|secret|token|api_key=<value>` k/v
  catch-all for anything the targeted patterns missed

Idempotent: redact(redact(x)) == redact(x). The replacement marker
contains no characters that match any pattern.
"""
from __future__ import annotations

import re


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # url_creds first — its capture would otherwise be eaten by
    # email or generic key=value patterns.
    (
        "url_creds",
        re.compile(
            r"\bhttps?://[A-Za-z0-9._~+\-]+:[^\s@/]+@[^\s]+",
        ),
    ),
    # JWT — three base64url segments separated by dots, starting eyJ.
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\b",
        ),
    ),
    # Bearer token — keep the "Bearer" label, drop the value.
    (
        "bearer",
        re.compile(
            r"(?i)\bbearer\s+[A-Za-z0-9._\-/+=]{8,}",
        ),
    ),
    # API keys by well-known provider prefix.
    (
        "api_key",
        re.compile(
            r"\b(?:sk_live_|sk_test_|pk_live_|pk_test_|"
            r"ghp_|ghs_|gho_|github_pat_|"
            r"AKIA|ASIA|"
            r"GOCSPX-|"
            r"xox[baprs]-)[A-Za-z0-9_\-]{8,}",
        ),
    ),
    # Generic k/v secrets — quoted or unquoted value, length ≥ 6.
    (
        "secret",
        re.compile(
            r"(?i)(?:password|passwd|secret|api[_\-]?key|access[_\-]?token|"
            r"auth[_\-]?token|client[_\-]?secret)"
            r"\s*[:=]\s*"
            r"[\"']?([A-Za-z0-9._\-/+=]{6,})[\"']?",
        ),
    ),
    # Email — local@domain.tld. Excludes `@param`/`@returns` style
    # via word-start and a dot in the domain.
    (
        "email",
        re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        ),
    ),
)


def redact(text: str) -> str:
    if not text:
        return text
    for kind, pattern in _PATTERNS:
        if kind == "bearer":
            text = pattern.sub(f"Bearer [REDACTED:{kind}]", text)
        elif kind == "secret":
            # Preserve the "<key>=" prefix; replace only the captured value.
            text = pattern.sub(
                lambda m: m.group(0).split(m.group(1))[0] + f"[REDACTED:{kind}]",
                text,
            )
        else:
            text = pattern.sub(f"[REDACTED:{kind}]", text)
    return text
