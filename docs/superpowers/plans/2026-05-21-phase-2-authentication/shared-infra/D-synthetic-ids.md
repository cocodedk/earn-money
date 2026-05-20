# Slice D — Synthetic identifier generation

> Lives in `backend/apps/stubs/_shared/auth/identifiers.py`.

## Surface

```python
def generate_invalid_identifier(
    kind: Literal["email", "username"],
    *,
    nonce: str | None = None,
) -> str
```

* `kind="email"` → `scanner-<nonce>@example.invalid`.
* `kind="username"` → `scanner_invalid_<nonce>`.
* `nonce` is auto-generated (16 hex chars from `secrets.token_hex(8)`)
  when omitted. Callers may inject a deterministic nonce for tests.

## Hard rules

* `example.invalid` is RFC 6761 reserved — no DNS lookup ever resolves
  it to a real address. Email sent there cannot leak to a real user.
* Usernames carry `scanner_invalid_` so any defender log shows the
  scanner trace cleanly. Visible. Auditable.
* Never use `admin`, `test`, `root`, `user`, `administrator`, etc.
  These are the FIRST values an attacker tries, and emitting them
  in an authorised scan tells the SOC "this might be hostile".
* No real users, no scraped emails, no leaked credentials. Period.

## Why one helper

Stubs 2.1 through 2.22 ALL generate invalid identifiers. One helper
guarantees the `example.invalid` invariant across every call site.
Letting each stub roll its own would eventually leak a non-RFC-6761
hostname.

## Tests

* Email format conforms to RFC 5322 + `@example.invalid` suffix.
* Username matches `scanner_invalid_[0-9a-f]{16}`.
* Two calls with no `nonce` produce different identifiers.
* Two calls with the same explicit `nonce` are identical (test
  determinism).
* `kind` outside the literal → `ValueError`.
