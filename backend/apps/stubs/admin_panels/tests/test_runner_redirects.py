"""Redirect-handling tests for stub 1.8 runner — same-origin admin
target heuristic and protocol-relative cross-origin guard."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.findings.models import Finding

from ..runner import run

from ._runner_helpers import make_nonce_bundle, make_probe, seed_for_1_8


_seed = seed_for_1_8
_nonce_bundle = make_nonce_bundle
_probe = make_probe


class RedirectTests(TestCase):
    def test_302_to_same_origin_admin_path_emits_medium(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={
                "/admin": _probe("", 302, location="/admin/login"),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/admin")
        assert finding.confidence == "medium"
        assert finding.data["signal_kind"] == "redirect_to_admin"

    def test_302_to_non_admin_path_skipped(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/admin": _probe("", 302, location="/login")},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_302_to_cross_origin_skipped(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={
                "/admin": _probe(
                    "", 302, location="https://other.example/admin",
                ),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_302_without_location_header_skipped(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/admin": _probe("", 302, location=None)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_302_with_absolute_same_origin_admin_url_fires(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={
                "/admin": _probe(
                    "", 302, location="https://x.example/admin/login",
                ),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.filter(data__path="/admin").exists()

    def test_302_protocol_relative_cross_origin_rejected(self) -> None:
        # `//host/path` is scheme-relative: the browser would resolve
        # it against the base URL's scheme but follow the (attacker-
        # controlled) host. The same-origin guard must normalise these
        # to absolute before comparing origins — otherwise a 302 to
        # `//attacker.example/admin` would slip through the
        # "no scheme → treat as relative" branch and emit a finding.
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={
                "/admin": _probe(
                    "", 302, location="//attacker.example/admin",
                ),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()
