"""Stub 1.17 FU-3 negative-assertion regression grid.

The spec §"Negative assertions" and §Safety enumerate "must not"
rules. Behavior is correct by construction today but had no tests
pinning it. This file locks each rule in place — drift here means
a regression that the suite catches before merge.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run

from ..runner import run


_BASE = "https://x.example"
_DJANGO_BODY = (
    "django.core.exceptions.ImproperlyConfigured: "
    "SECRET_KEY setting must not be empty"
)


def _resp(body: str, *, status: int = 200, url: str | None = None,
          content_type: str = "application/json",
          extra_headers: dict[str, str] | None = None) -> httpx.Response:
    headers = {"content-type": content_type}
    if extra_headers:
        headers.update(extra_headers)
    return httpx.Response(
        status_code=status, headers=headers,
        content=body.encode("utf-8"),
        request=httpx.Request("GET", url or f"{_BASE}/"),
    )


@contextmanager
def _mock_fetcher(get_handler):
    with patch(
        "apps.stubs.verbose_api_errors.fetcher.httpx.Client",
    ) as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = get_handler
        yield mock_client, instance


def _seed(host: str = "x.example"):
    return seed_target_run(stub_slug="1.17", host=host)


class HttpMethodSafetyTests(TestCase):
    """Spec §Safety: the detector must only send GET (and OPTIONS
    in FU-deferred work). Mutating methods are explicitly forbidden."""

    def test_only_get_is_issued_across_both_probes(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp("ok", status=200, url=str(url))

        with _mock_fetcher(handler) as (_client, instance):
            run(scan_run, target_run)

        # `get` was called twice (baseline + nonexistent_api_sibling).
        assert instance.get.call_count == 2
        # No mutating method may ever be invoked on the client.
        for forbidden in ("post", "put", "patch", "delete", "request"):
            method = getattr(instance, forbidden)
            assert method.called is False, (
                f"runner must not call client.{forbidden}() — "
                f"spec §Safety forbids mutating HTTP methods"
            )

    def test_no_request_body_is_attached(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp("ok", status=200, url=str(url))

        with _mock_fetcher(handler) as (_client, instance):
            run(scan_run, target_run)

        # Spec §"Probe plan" line: "Do not send request bodies".
        # No call should pass a body kwarg (data / json / content).
        for call in instance.get.call_args_list:
            for forbidden_kwarg in ("data", "json", "content"):
                assert forbidden_kwarg not in call.kwargs, (
                    f"runner must not attach `{forbidden_kwarg}=` "
                    f"to GET — spec §Probe plan forbids request bodies"
                )


class RedirectPolicyTests(TestCase):
    """Spec §config: `follow_redirects=False`. Off-origin chases
    are forbidden by §Safety."""

    def test_follow_redirects_is_false(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp("ok", status=200, url=str(url))

        with _mock_fetcher(handler) as (client, _instance):
            run(scan_run, target_run)

        # Client constructor must be called with follow_redirects=False.
        for call in client.call_args_list:
            assert call.kwargs.get("follow_redirects") is False, (
                "fetcher must construct httpx.Client with "
                "follow_redirects=False per spec §config"
            )


class AiAssistanceMarkerTests(TestCase):
    """Spec §Persistence: every finding records `ai_assistance: "none"`.
    No AI/LLM is allowed in the detection path."""

    def test_persisted_finding_marks_ai_assistance_none(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(
                _DJANGO_BODY, status=500, url=str(url),
                content_type="text/plain",
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        finding = Finding.objects.filter(scan_run=scan_run).first()
        assert finding is not None
        assert finding.data["ai_assistance"] == "none"


class HostnameAgnosticTests(TestCase):
    """Spec §Safety: hostname must not influence detection.
    Identical body on two different hostnames must yield the same
    indicator stream."""

    def test_same_body_same_finding_across_hosts(self) -> None:
        def handler(url, **_kwargs):
            return _resp(
                _DJANGO_BODY, status=500, url=str(url),
                content_type="text/plain",
            )

        results: list[set[str]] = []
        for host in ("alpha.example", "beta.example"):
            scan_run, target_run = _seed(host=host)
            with _mock_fetcher(handler):
                run(scan_run, target_run)
            finding = Finding.objects.filter(scan_run=scan_run).first()
            assert finding is not None
            results.append(set(finding.data["framework_hints"]))

        assert results[0] == results[1]


class WeakSignalTests(TestCase):
    """Spec §"Negative assertions": these responses must NOT create
    a finding even if they superficially look like errors."""

    def test_rfc_7807_problem_details_no_finding(self) -> None:
        scan_run, target_run = _seed()
        body = (
            '{"type": "https://example.com/probs/oops", '
            '"title": "Bad Request", "status": 400, '
            '"detail": "field is required"}'
        )

        def handler(url, **_kwargs):
            return _resp(
                body, status=400, url=str(url),
                content_type="application/problem+json",
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        # Evidence is still recorded (operator triage benefits).
        assert Evidence.objects.filter(scan_run=scan_run).count() == 2

    def test_server_header_alone_no_finding(self) -> None:
        scan_run, target_run = _seed()

        def handler(url, **_kwargs):
            return _resp(
                "ok", status=200, url=str(url),
                content_type="text/plain",
                extra_headers={"Server": "nginx/1.21.6"},
            )

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        # Server: nginx alone is not a finding — spec §"Negative
        # assertions" line 393.
        assert Finding.objects.filter(scan_run=scan_run).count() == 0

    def test_validation_error_without_internals_no_finding(self) -> None:
        scan_run, target_run = _seed()
        body = (
            '{"errors": [{"field": "email", "message": '
            '"is required"}]}'
        )

        def handler(url, **_kwargs):
            return _resp(body, status=422, url=str(url))

        with _mock_fetcher(handler):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
