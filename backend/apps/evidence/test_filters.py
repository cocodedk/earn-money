"""Filter contract tests for `/api/evidence/` — the new project filter
that the 9-slice (Evidence standalone) depends on.
"""
from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.evidence.models import Evidence, EvidenceSource
from apps.stubs._test_factories import seed_target_run


class EvidenceFilterTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.sr_a, self.tr_a = seed_target_run(stub_slug="1.1", host="a.test")
        self.sr_b, self.tr_b = seed_target_run(stub_slug="1.2", host="b.test")
        self.e_a = Evidence.objects.create(
            scan_run=self.sr_a, target=self.tr_a.target,
            source=EvidenceSource.HTML, url="https://a.test/", method="GET",
            field="x", matched_value="y", raw_excerpt="z", content_hash="",
            data={},
        )
        self.e_b = Evidence.objects.create(
            scan_run=self.sr_b, target=self.tr_b.target,
            source=EvidenceSource.HTML, url="https://b.test/", method="GET",
            field="x", matched_value="y", raw_excerpt="z", content_hash="",
            data={},
        )

    def _ids(self, response) -> set[str]:
        return {row["id"] for row in response.json()["results"]}

    def test_filter_by_project(self) -> None:
        resp = self.client.get(f"/api/evidence/?project={self.sr_a.project_id}")
        assert self._ids(resp) == {str(self.e_a.id)}

    def test_combined_project_and_target(self) -> None:
        # AND semantics — project A AND target B = empty
        resp = self.client.get(
            f"/api/evidence/?project={self.sr_a.project_id}"
            f"&target={self.tr_b.target_id}"
        )
        assert self._ids(resp) == set()
