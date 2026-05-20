"""API tests for the Stubs ViewSet — written BEFORE the viewset.

Uses `override_settings(COOKBOOK_ROOT=tmpdir)` so tests don't depend on
the real cookbook tree on disk. The registry is keyed by path internally,
so a fresh tmpdir per test class gets a fresh registry.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .tests import write_stub


class StubApiTests(APITestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.tmpdir = tempfile.mkdtemp()
        cls.root = Path(cls.tmpdir)
        write_stub(cls.root, phase=1, spec=1, phase_slug="information-gathering", slug="framework-detection", title="Framework detection", phase_title="Information gathering", category="Technology fingerprinting")
        write_stub(cls.root, phase=1, spec=2, phase_slug="information-gathering", slug="server-headers", title="Server headers", phase_title="Information gathering", category="Technology fingerprinting")
        cls._override = override_settings(COOKBOOK_ROOT=cls.tmpdir)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._override.disable()
        shutil.rmtree(cls.tmpdir, ignore_errors=True)
        super().tearDownClass()

    def test_list_returns_all_stubs_without_body(self) -> None:
        r = self.client.get(reverse("stub-list"))
        assert r.status_code == status.HTTP_200_OK
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) == 2
        for row in rows:
            assert "body" not in row
            assert {"slug", "phase", "spec", "title", "status", "fixture",
                    "category", "phase_title", "phase_slug", "spec_slug",
                    "path"}.issubset(row.keys())

    def test_list_is_sorted_by_phase_spec(self) -> None:
        r = self.client.get(reverse("stub-list"))
        slugs = [row["slug"] for row in r.json()]
        assert slugs == ["1.1", "1.2"]

    def test_retrieve_returns_full_stub_with_body(self) -> None:
        r = self.client.get(reverse("stub-detail", args=["1.1"]))
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["slug"] == "1.1"
        assert body["title"] == "Framework detection"
        assert "body" in body
        assert "Body text" in body["body"]

    def test_retrieve_unknown_slug_returns_404(self) -> None:
        r = self.client.get(reverse("stub-detail", args=["9.99"]))
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert "detail" in r.json()

    def test_post_to_list_returns_405(self) -> None:
        r = self.client.post(reverse("stub-list"), {}, format="json")
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_to_detail_returns_405(self) -> None:
        r = self.client.put(
            reverse("stub-detail", args=["1.1"]), {}, format="json"
        )
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_to_detail_returns_405(self) -> None:
        r = self.client.delete(reverse("stub-detail", args=["1.1"]))
        assert r.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
