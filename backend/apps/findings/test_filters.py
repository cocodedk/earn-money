"""Filter contract tests for `/api/findings/` — the new project /
target / severity / confidence / stub aliases that 6-D and downstream
8 / 9 slices depend on.
"""
from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run


class FindingFilterTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.sr_a, self.tr_a = seed_target_run(stub_slug="1.1", host="a.test")
        self.sr_b, self.tr_b = seed_target_run(stub_slug="1.2", host="b.test")
        self.f_a_low = Finding.objects.create(
            scan_run=self.sr_a, target=self.tr_a.target,
            stub_slug="1.1", category="framework",
            severity="low", confidence="low",
            title="A low/low", data={},
        )
        self.f_a_high = Finding.objects.create(
            scan_run=self.sr_a, target=self.tr_a.target,
            stub_slug="1.1", category="framework",
            severity="medium", confidence="high",
            title="A med/high", data={},
        )
        self.f_b = Finding.objects.create(
            scan_run=self.sr_b, target=self.tr_b.target,
            stub_slug="1.2", category="server_headers",
            severity="info", confidence="high",
            title="B info/high", data={},
        )

    def _ids(self, response) -> set[str]:
        return {row["id"] for row in response.json()["results"]}

    def test_filter_by_project(self) -> None:
        resp = self.client.get(f"/api/findings/?project={self.sr_a.project_id}")
        ids = self._ids(resp)
        assert str(self.f_a_low.id) in ids
        assert str(self.f_a_high.id) in ids

    def test_filter_by_target(self) -> None:
        resp = self.client.get(f"/api/findings/?target={self.tr_b.target_id}")
        assert self._ids(resp) == {str(self.f_b.id)}

    def test_filter_by_severity(self) -> None:
        resp = self.client.get("/api/findings/?severity=medium")
        assert self._ids(resp) == {str(self.f_a_high.id)}

    def test_filter_by_confidence(self) -> None:
        resp = self.client.get("/api/findings/?confidence=low")
        assert self._ids(resp) == {str(self.f_a_low.id)}

    def test_filter_by_stub_alias(self) -> None:
        # Both `?stub=` and `?stub_slug=` resolve to the same field.
        a = self._ids(self.client.get("/api/findings/?stub=1.2"))
        b = self._ids(self.client.get("/api/findings/?stub_slug=1.2"))
        assert a == b == {str(self.f_b.id)}

    def test_combined_filters_are_AND(self) -> None:
        # severity=medium AND confidence=low → empty (no row matches both).
        resp = self.client.get("/api/findings/?severity=medium&confidence=low")
        assert self._ids(resp) == set()
