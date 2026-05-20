"""End-to-end orchestration tests for `well_known_paths.runner.run`.

Soft-404 prelude → per-family iteration → fetcher → classify → redact
→ persist Evidence + Finding rows.

Spec sources: 1.20-1.25.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx

from django.test import TestCase

from apps.events.models import Event
from apps.events.types import EventType
from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus
from apps.stubs._test_factories import seed_target_run

from ..runner import run


_BASE = "https://x.example"


def _r(status: int, *, url: str, body: bytes = b"",
       content_type: str = "text/plain") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"content-type": content_type},
        content=body,
        request=httpx.Request("HEAD", url),
    )


@contextmanager
def _mock_client(head_handler, get_handler):
    with patch("apps.stubs.well_known_paths.fetcher.httpx.Client") as mc:
        instance = mc.return_value.__enter__.return_value
        instance.head.side_effect = head_handler
        instance.get.side_effect = get_handler
        yield instance


def _seed():
    return seed_target_run(stub_slug="1.20", host="x.example")


class SoftFootprintPreludeTests(TestCase):
    def test_baseline_probe_seeds_footprint(self) -> None:
        scan_run, target_run = _seed()
        # Every HEAD/GET returns the same SPA shell — every candidate
        # should be rejected by soft-404 match.
        spa = b"<html><body>SPA shell content here</body></html>" + b" " * 200

        def head(url, **_): return _r(200, url=str(url))
        def get(url, **_): return _r(200, url=str(url), body=spa,
                                     content_type="text/html")

        with _mock_client(head, get):
            run(scan_run, target_run)

        # All probes match the SPA footprint → zero findings.
        assert Finding.objects.filter(scan_run=scan_run).count() == 0


class EnvHitTests(TestCase):
    def test_env_file_at_root_yields_finding(self) -> None:
        scan_run, target_run = _seed()
        env_body = b"DB_PASSWORD=secret\nAPI_KEY=abc123\n"

        def head(url, **_): return _r(200, url=str(url))

        def get(url, **_):
            url_str = str(url)
            if "scanner_nonexistent" in url_str:
                return _r(404, url=url_str)  # baseline 404 → distinct footprint
            if url_str.endswith("/.env"):
                return _r(200, url=url_str, body=env_body,
                          content_type="text/plain")
            return _r(404, url=url_str)

        with _mock_client(head, get):
            run(scan_run, target_run)

        findings = Finding.objects.filter(scan_run=scan_run)
        assert findings.count() >= 1
        env_finding = next(
            (f for f in findings if f.data.get("family") == "env"), None,
        )
        assert env_finding is not None
        assert env_finding.status == FindingStatus.CANDIDATE
        assert env_finding.category == "well_known_paths.env"
        # Redaction ran before persist — no raw secret in excerpt.
        assert "secret" not in env_finding.data["redacted_excerpt"]
        assert "DB_PASSWORD=<REDACTED>" in env_finding.data["redacted_excerpt"]


class CleanTargetTests(TestCase):
    def test_clean_target_yields_evidence_no_findings(self) -> None:
        scan_run, target_run = _seed()

        def head(url, **_): return _r(404, url=str(url))
        def get(url, **_):  # pragma: no cover — HEAD 404 short-circuits
            return _r(404, url=str(url))

        with _mock_client(head, get):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        # Evidence still recorded for every probe (baseline + each
        # candidate path across all families).
        assert Evidence.objects.filter(scan_run=scan_run).count() > 0


class CandidateBodyNoSignatureTests(TestCase):
    def test_candidate_with_body_but_no_signature_emits_no_finding(self) -> None:
        """Cover the `verdict is None: continue` branch — a fetched body
        that doesn't match the soft-404 footprint AND doesn't match
        any family signature."""
        scan_run, target_run = _seed()

        def head(url, **_): return _r(200, url=str(url))

        def get(url, **_):
            url_str = str(url)
            if "scanner_nonexistent" in url_str:
                # Distinct baseline so candidates don't match its footprint.
                return _r(200, url=url_str,
                          body=b"baseline-shell" + b" " * 500)
            # All real candidates return a totally unrelated body
            # (no env KV, no git ref, no SQL, no log timestamps).
            return _r(200, url=url_str, body=b"<html><body>boring</body></html>")

        with _mock_client(head, get):
            run(scan_run, target_run)

        # No findings (no signature fires) — but every candidate's
        # Evidence row was written.
        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        assert Evidence.objects.filter(scan_run=scan_run).count() > 0

class ScopeRejectionTests(TestCase):
    """Slice E: enforce_scope wired into the fetcher path."""

    def test_baseline_out_of_scope_returns_early(self) -> None:
        """If the BASELINE URL is rejected (mocked scenario where the
        target host is out-of-scope), the runner exits without issuing
        any HTTP and without writing any Evidence/Finding rows."""
        # Seed a target on an out-of-scope host ("unknown.invalid" — the
        # conftest default program lists *.invalid in_scope, so let's
        # use a domain it doesn't cover).
        from apps.programs import loader
        loader._default_registry = None
        scan_run, target_run = seed_target_run(
            stub_slug="1.20", host="out-of-scope.unmatched",
        )

        def head(url, **_): return _r(200, url=str(url))  # pragma: no cover — bypassed
        def get(url, **_): return _r(200, url=str(url))  # pragma: no cover

        # The runner's find_for_host will raise OutOfScope before any
        # HTTP. The exception propagates out — the runner doesn't
        # catch it because it shouldn't have reached this point past
        # pre-flight. Wrap accordingly.
        from apps.programs.exceptions import OutOfScope as OOS
        with _mock_client(head, get), self.assertRaises(OOS):
            run(scan_run, target_run)
        assert Evidence.objects.filter(scan_run=scan_run).count() == 0


    def test_in_scope_baseline_proceeds_with_no_oos_event(self) -> None:
        """In-scope target produces ZERO OUT_OF_SCOPE_REJECTED events;
        the runner's per-candidate enforce_scope is exercised but every
        check passes."""
        scan_run, target_run = _seed()
        def head(url, **_): return _r(200, url=str(url))
        def get(url, **_): return _r(200, url=str(url), body=b"")
        with _mock_client(head, get):
            run(scan_run, target_run)
        assert Event.objects.filter(
            scan_run=scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
        ).count() == 0

    def test_baseline_enforce_scope_raises_returns_early(self) -> None:
        """Defensive branch: enforce_scope on the baseline URL raises
        despite find_for_host having resolved the target. Runner exits
        without hitting any fetcher."""
        scan_run, target_run = _seed()
        with patch(
            "apps.stubs.well_known_paths.runner.guard",
            side_effect=__import__(
                "apps.programs.exceptions", fromlist=["OutOfScope"],
            ).OutOfScope("synthetic baseline reject"),
        ):
            def head(url, **_):  # pragma: no cover — fetcher never called
                return _r(200, url=str(url))
            def get(url, **_):  # pragma: no cover
                return _r(200, url=str(url))
            with _mock_client(head, get):
                run(scan_run, target_run)
        assert Evidence.objects.filter(scan_run=scan_run).count() == 0

    def test_candidate_enforce_scope_raises_continues_to_next(self) -> None:
        """Defensive branch: baseline passes, then a candidate URL's
        enforce_scope raises. Runner logs event (via the mocked
        function) and continues — no Evidence row for the rejected
        candidate."""
        from apps.programs.exceptions import OutOfScope as OOS
        scan_run, target_run = _seed()
        call_count = {"n": 0}

        def fake_enforce(program, target, url, *, scan_run=None, stub_id=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None  # baseline passes
            raise OOS("synthetic candidate reject")

        with patch(
            "apps.stubs.well_known_paths.runner.guard",
            side_effect=fake_enforce,
        ):
            def head(url, **_): return _r(404, url=str(url))
            def get(url, **_):  # pragma: no cover — baseline doesn't pass scope yet
                return _r(404, url=str(url))
            with _mock_client(head, get):
                run(scan_run, target_run)
        # Baseline went through fetcher; subsequent candidates all
        # rejected → only baseline Evidence (if any) was written.
        assert Finding.objects.filter(scan_run=scan_run).count() == 0

