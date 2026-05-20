# Slice A — Auth-form discovery

> Lives in `backend/apps/stubs/_shared/auth/forms.py`.
> Used by every Phase 2 stub that needs to find a login / reset /
> registration / OAuth-callback form.

## Surface

```python
@dataclass(frozen=True)
class AuthForm:
    method: Literal["GET", "POST"]
    action_url: str           # absolute URL after urljoin
    content_type: str         # "application/x-www-form-urlencoded" | "application/json"
    identifier_field: str     # the name of the username/email input
    password_field: str | None
    hidden_fields: dict[str, str]  # CSRF, request-id, etc. (values redacted in evidence)
    flow_hint: Literal["login", "password_reset", "registration", "oauth", "unknown"]

def discover_forms(html_body: str, base_url: str) -> list[AuthForm]
def discover_json_endpoint(...)  # JSON-only auth APIs
```

## Detection signals (spec 2.1 §1)

A page becomes an auth candidate when ANY of:

* An HTML `<form>` with a `<input type="password">`.
* An HTML `<form>` with an input named `username | email | login | identifier | user | account`.
* A JSON endpoint route or response evidence suggesting login.
* A page `<title>`, label, button, or `<form action>` indicating sign-in.

`flow_hint` is inferred from the same signals plus action-URL keywords
(`login | signin | reset | register | callback | oauth`). It's **a hint**,
not authoritative — stub-level logic still treats the form generically.

## What this is NOT

* Not technology detection. The form parser doesn't care what framework
  rendered the form. No "if Django then ..." or "if Rails then ...".
* Not JS rendering. SPAs that hydrate forms client-side return a sparse
  HTML body; `discover_forms` returns `[]` and the runner emits
  `AUTH_FIXTURE_REQUIRED` with `reason="requires_js_rendering"`.

## Tests

* Form with `<input type="password">` → discovered.
* Form with `<input name="email">` + no password → discovered with
  `password_field=None`, `flow_hint="password_reset"` if action-URL has
  "reset".
* Multiple forms on one page → all returned, sorted by visible-form
  preference (login before nav forms).
* CSRF hidden inputs captured in `hidden_fields`.
* Empty body / non-HTML content-type → `[]`.

## Why centralise

Stubs 2.1 through 2.22 all need to discover at least one auth form. A
shared parser means signature consistency, one set of tests, and one
place to handle pathological HTML (mid-document encoding switches,
script-rewritten forms, etc.).
