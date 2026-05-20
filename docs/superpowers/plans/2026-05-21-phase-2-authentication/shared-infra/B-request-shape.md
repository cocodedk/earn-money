# Slice B — Request-shape preservation

> Lives in `backend/apps/stubs/_shared/auth/requests.py`.
> Used by stubs that submit comparable probes (2.1 / 2.2 / 2.3 / 2.4 / 2.5).

## Surface

```python
@dataclass(frozen=True)
class ProbePair:
    """A matched invalid-control + valid-control probe pair, built from
    one AuthForm. The shape is identical except for the identifier value."""
    form: AuthForm
    invalid_request: Request   # with synthetic identifier
    valid_request: Request | None  # None when no scoped valid id available

def build_probe_pair(
    form: AuthForm,
    invalid_identifier: str,
    valid_identifier: str | None,
    bogus_password: str,
    csrf_refresh: Callable[[], dict[str, str]] | None = None,
) -> ProbePair
```

## Shape-preservation rules (spec 2.1 §2.6)

Both requests in a `ProbePair` share:

* Same HTTP method.
* Same parameter names (only the identifier value differs).
* Same content type.
* Same header set, EXCEPT for dynamic cookies + per-request CSRF tokens.
* Same redirect policy (controlled by the caller; default no-follow).
* Same User-Agent (Phase 2 sets a stable scanner UA: `cookbook-scanner/v2 (+https://cocode.dk)`).

Credential-bearing login/reset/register forms are submitted only when
`form.method == "POST"`. If discovery finds a `GET` credential form, the
runner records `AUTH_PROBE_REFUSED` with `reason="unsafe_method"` via
[`F-active-safety`](F-active-safety.md) and sends no active request.

Per-request dynamic re-fetch:

* If the form has hidden CSRF inputs, the caller passes `csrf_refresh` so
  each submit gets a fresh token from a fresh GET. Without that, CSRF
  re-use will void the comparison.

Execution isolation:

* The invalid-control and valid-control submits use isolated cookie jars.
  The only shared state is the static request shape and the per-request CSRF
  values fetched by `csrf_refresh`.
* Redirect following defaults to off for comparison probes. If a stub needs
  redirects, it must compare the normalized final URL and redacted redirect
  chain rather than raw response bytes.
* The helper constructs request objects only. Network execution remains in
  the runner after scope, RoE, rate-limit, and safety gates pass.

## Why centralise

Every comparison-based stub needs this exact preservation. Letting each
stub roll its own ProbePair builder guarantees one stub will mistake a
CSRF-token diff for a real differentiator and emit a false positive.

## Tests

* `build_probe_pair` with no `valid_identifier` returns `valid_request=None`.
* Both requests carry identical headers + identical method + identical
  content type.
* CSRF refresh callback fires once per request, not once per pair.
* Invalid and valid requests do not share cookies or mutated session state.
* `GET` credential form path refuses before request execution.
* `_shared/http.guard` runs before any HTTP fires (already enforced at
  the runner layer; this helper is pre-network).
