# Task 10c — Stub 2.17: detection chain + commit

**Part 2 of 2 for Step 5.**
Wire the detection chain in `runner.py`, add the `_emit_link_finding` helper, run coverage, and commit.

**Continues from:** [10b-runner-tests.md](10b-runner-tests.md)

---

- [ ] **Step 5b: Wire detection chain in runner.py**

Add these imports at the top of `runner.py` so tests can patch them:

```python
import os
import httpx
from apps.stubs._shared.auth.requests import submit_probe
from apps.programs.rate_limit import acquire_for
from apps.findings.models import Finding, FindingStatus, Severity
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.targets.models import ScanTarget
from .classify import classify_link_flaw
```

In `backend/apps/stubs/oauth_account_linking/runner.py`, replace the stub `return` with:

```python

    _STUB_ID = "2.17"
    fixture_url = os.environ.get("FIXTURE_OAUTH_ACCOUNT_LINK_URL", target.base_url)
    accounts = program.roe.authorized_test_accounts
    if not accounts:
        return

    with httpx.Client(follow_redirects=False, timeout=10) as http:
        login = http.post(
            fixture_url.rstrip("/") + "/login",
            json={
                "username": accounts[0],
                "password": os.environ.get("FIXTURE_OAUTH_ACCOUNT_LINK_PASS_A", "pass-a"),
            },
        )
    if login.status_code != 200:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.TRANSPORT_ERROR,
            details={"detail": "fixture_login_failed"},
        )
        return
    session_headers = {"X-Session-Token": login.json().get("token", "")}

    _CANDIDATE_PROBES = [
        ("GET", "/auth/link/start", None, False),
        ("GET", "/settings/connections/link/mock", None, False),
        ("POST", "/auth/link/callback", {"code": "code-fixture"}, True),
        ("GET", "/auth/link/callback-client-id?provider_user_id=scanner-controlled", None, False),
        ("GET", "/settings/connections", None, False),
    ]

    for method, path, json_body, no_csrf_sent in _CANDIDATE_PROBES:
        acquire_for(program)
        # Use submit_probe to get raw httpx.Response with headers (needed for 302 Location)
        request_kwargs = {"headers": session_headers}
        if json_body is not None:
            request_kwargs["json"] = json_body
        request = httpx.Request(
            method, fixture_url.rstrip("/") + path,
            **request_kwargs,
        )
        resp = submit_probe(request)
        if resp is None:
            record_refusal(
                scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
                reason=RefusalReason.TRANSPORT_ERROR,
                details={"detail": f"target_unreachable:{path}"},
            )
            return

        flaw = classify_link_flaw(
            resp,
            endpoint_url=fixture_url.rstrip("/") + path,
            no_csrf_sent=no_csrf_sent,
        )
        if flaw is not None:
            _emit_link_finding(
                scan_run=scan_run, target=target, flaw=flaw,
            )
            return
```

- [ ] **Step 5c: Add `_emit_link_finding` helper**

```python
def _emit_link_finding(*, scan_run, target, flaw) -> None:
    from apps.findings.models import Finding, FindingStatus, Severity
    from apps.stubs._shared.auth.events import log_finding_candidate
    finding = Finding.objects.create(
        scan_run=scan_run, target=target, stub_slug="2.17",
        title=f"Account-linking flaw: {flaw.kind.value}",
        category="oauth_account_linking_flaws",
        severity=Severity.MEDIUM,
        confidence=flaw.confidence,
        status=FindingStatus.CANDIDATE,
        data={
            "kind": flaw.kind.value,
            "endpoint": flaw.endpoint_url,
            "method": flaw.http_method,
            "requires_manual_review": True,
        },
    )
    log_finding_candidate(finding, stub_id="2.17")
```

- [ ] **Step 6: Run tests + coverage**

```bash
cd backend && python -m pytest apps/stubs/oauth_account_linking/ -v --tb=short
cd backend && python -m pytest apps/stubs/oauth_account_linking/ \
  --cov=apps/stubs/oauth_account_linking --cov-report=term-missing
```

- [ ] **Step 7: Commit**

```bash
git add backend/apps/stubs/oauth_account_linking/
git commit -m "feat(stubs): 2.17 oauth-account-linking — passive discovery + classify"
```

---

## After Task 10

Run `/codex-review` on the complete OAuth family (stubs 2.14–2.17 +
fixture), then iterate `/code-review high` until clean.

Update cookbook spec frontmatter for 2.14–2.17 to `status: done`.

Run `scripts/cookbook_progress.py` to regenerate `PROGRESS.md`.

Commit: `docs(progress): Phase 2 OAuth family 2.14-2.17 done`.
