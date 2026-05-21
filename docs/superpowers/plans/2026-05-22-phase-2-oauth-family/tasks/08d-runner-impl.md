# Task 08d — Stub 2.14: runner.py detection chain + coverage + commit

**Part of:** Task 08 — Stub 2.14: oauth-redirect-uri detection chain

**Files:**
- Modify: `backend/apps/stubs/oauth_redirect_uri/runner.py`

**Continues from:** [08c-runner.md](08c-runner.md)

---

- [ ] **Step 9b: Implement detection chain in `runner.py`**

Add these imports at the top of `runner.py` so the tests can patch them:

```python
import os
import json
import secrets
import httpx
from apps.stubs._shared.auth.discovery import fetch_for_discovery
from apps.stubs._shared.auth.requests import submit_probe
from apps.programs.rate_limit import acquire_for
from apps.findings.models import Finding, FindingStatus, Severity
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.targets.models import ScanTarget
from .mutate import generate_mutations
from .classify import classify_redirect_response
```

Replace `return` placeholder at end of `runner.py` with:

```python

    _STUB_ID = "2.14"
    _SCANNER_ORIGIN = os.environ.get("SCANNER_REDIRECT_ORIGIN", "https://scanner.invalid")
    fixture_url = os.environ.get("FIXTURE_OAUTH_REDIRECT_URI_URL", target.base_url)

    # OIDC discovery — FetchOutcome.body contains the JSON document
    acquire_for(program)
    oidc_resp = fetch_for_discovery(
        fixture_url + "/.well-known/openid-configuration",
        target=target, program=program,
    )
    if not oidc_resp.ok:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "oidc_discovery_unreachable"},
        )
        return

    try:
        doc = json.loads(oidc_resp.body)
    except Exception:
        return

    primary_endpoint = doc.get("authorization_endpoint", "")
    auth_endpoints = [
        ep for ep in [primary_endpoint, *doc.get("authorization_endpoint_variants", [])]
        if ep
    ]
    if not auth_endpoints:
        return

    # Baseline redirect URI from OIDC doc or config default
    baseline_redirect = os.environ.get(
        "FIXTURE_OAUTH_KNOWN_REDIRECT_URI",
        "https://app.example.test/oauth/callback",
    )
    client_id = os.environ.get("FIXTURE_OAUTH_CLIENT_ID", "test-client")

    mutations = generate_mutations(
        baseline_redirect_uri=baseline_redirect,
        scanner_origin=_SCANNER_ORIGIN,
        max_probes=8,
    )

    first_candidate = None
    for auth_endpoint in auth_endpoints:
        for mutation in mutations:
            acquire_for(program)
            # submit_probe must preserve 3xx responses; do not follow redirects.
            request = httpx.Request(
                "GET", auth_endpoint,
                params={
                    "client_id": client_id,
                    "redirect_uri": mutation.mutated_uri,
                    "response_type": "code",
                    "state": secrets.token_hex(8),
                },
            )
            resp = submit_probe(request)
            if resp is None:
                continue
            classification = classify_redirect_response(resp, _SCANNER_ORIGIN)
            if classification.status == "confirmed":
                _emit_finding_redirect(
                    scan_run=scan_run, target=target,
                    auth_endpoint=auth_endpoint,
                    mutation_class=mutation.mutation_class.value,
                    classification=classification,
                )
                return  # One confirmed finding per target is enough
            if classification.status == "candidate" and first_candidate is None:
                first_candidate = (auth_endpoint, mutation, classification)

    if first_candidate is not None:
        auth_endpoint, mutation, classification = first_candidate
        _emit_finding_redirect(
            scan_run=scan_run, target=target,
            auth_endpoint=auth_endpoint,
            mutation_class=mutation.mutation_class.value,
            classification=classification,
        )
```

Add helper at bottom of `runner.py`:

```python
def _emit_finding_redirect(
    *, scan_run, target, auth_endpoint, mutation_class, classification,
) -> None:
    from apps.stubs._shared.auth.events import log_finding_candidate
    from apps.findings.models import Finding, FindingStatus, Severity
    severity = Severity.HIGH if classification.status == "confirmed" else Severity.MEDIUM
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.14",
        title="OAuth redirect URI validation weakness",
        category="oauth_redirect_uri_issues",
        severity=severity,
        confidence=classification.confidence,
        status=FindingStatus.CANDIDATE,
        data={
            "auth_endpoint": auth_endpoint,
            "mutation_class": mutation_class,
            "location_origin": classification.location_origin,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id="2.14")
```

- [ ] **Step 10: Run full test suite and coverage**

```bash
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/ -v --tb=short
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/ \
  --cov=apps/stubs/oauth_redirect_uri --cov-report=term-missing
# Expected: 100% coverage
```

- [ ] **Step 11: Commit**

```bash
git add backend/apps/stubs/oauth_redirect_uri/
git commit -m "feat(stubs): 2.14 oauth-redirect-uri — mutation + classification + detection chain"
```
