# Slice C — Response normalization

> Lives in `backend/apps/stubs/_shared/auth/normalize.py`.
> Used by every comparison-based Phase 2 stub.

## Why

Two probes against the same endpoint return responses whose bytes differ
on every request even when the underlying behaviour is identical: CSRF
tokens, request IDs, timestamps, nonces, UUIDs, session cookies, dynamic
counters. Without normalization a stub would emit `body_length_diff: 17 bytes`
as a "differentiator" on every comparison.

## Surface

```python
@dataclass(frozen=True)
class NormalizedResponse:
    status: int
    final_url: str            # final after redirects (caller chose policy)
    redirect_location: str | None
    content_type: str
    title: str | None         # <title> if HTML
    body_fingerprint: str     # sha256 of normalized body
    body_snippet: str         # ~512 chars near "error" / "invalid" / "incorrect"
    json_error_code: str | None
    json_error_fields: dict[str, str]   # field-level errors

def normalize(response: httpx.Response) -> NormalizedResponse
def diff(a: NormalizedResponse, b: NormalizedResponse) -> list[Differentiator]
```

## What `normalize` strips (spec 2.1 §4)

* CSRF values (hidden-input pattern matching).
* Request IDs / trace IDs (`X-Request-ID`, `X-Trace-ID`, etc.).
* Session IDs (`session`, `sessionid` cookies; `Set-Cookie` values).
* Timestamps (ISO-8601 + Unix-epoch + RFC-1123 patterns).
* Nonces (input fields named `nonce`, `csrfmiddlewaretoken`, etc.).
* UUIDs (`[0-9a-f-]{32,36}` patterns).
* Random-looking high-entropy tokens (lookup table of known framework patterns).
* HTML whitespace differences (collapse runs to single space).

## What `diff` keeps

* HTTP status.
* Redirect target path + query KEYS (values redacted).
* JSON error codes + field names.
* Form-level + field-level error messages.
* Response `<title>`.
* Stable body-text snippets around the error area.
* Content-type.
* Headers that affect control flow (`Location`, `WWW-Authenticate`).

## Tests

* Two identical responses with different CSRF tokens diff to `[]`.
* Two responses with status 401 vs 404 diff to one `status_code` entry.
* `Set-Cookie: session=...` differences are stripped.
* `WWW-Authenticate: Basic realm=...` change → kept.

## Why one module, not per-stub

The normalizer needs the same allowlist for every probe pair. If stub
2.1 strips CSRF but stub 2.5 doesn't, then 2.5 will report false
positives. One normalizer = one allowlist = consistent behaviour.
