"""Tests for spec 03-targets.md `host optional` / `ip optional` —
the create endpoint must accept blank/missing/null values and
derive a sensible host from base_url server-side."""
from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.projects.models import Project
from apps.targets.models import ScanTarget


class CreateTargetWithOptionalHostTests(APITestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="acme")

    def _payload(self, **overrides) -> dict:
        base = {
            "project": str(self.project.id),
            "base_url": "https://dvwa.cocode.dk",
        }
        base.update(overrides)
        return base

    def test_create_with_host_omitted(self) -> None:
        # Spec: form lets the user skip host. Backend derives it from
        # base_url's netloc (without port) so the stored row is
        # meaningful even when the operator typed only the URL.
        r = self.client.post(
            reverse("target-list"), self._payload(), format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED, r.content
        body = r.json()
        assert body["host"] == "dvwa.cocode.dk"

    def test_create_with_host_empty_string(self) -> None:
        r = self.client.post(
            reverse("target-list"), self._payload(host=""), format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED, r.content
        assert r.json()["host"] == "dvwa.cocode.dk"

    def test_create_with_host_null(self) -> None:
        r = self.client.post(
            reverse("target-list"), self._payload(host=None), format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED, r.content
        assert r.json()["host"] == "dvwa.cocode.dk"

    def test_create_with_ip_omitted(self) -> None:
        # Spec: ip is optional too. ip stays null when omitted.
        r = self.client.post(
            reverse("target-list"), self._payload(), format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.json()["ip"] is None

    def test_create_with_ip_blank(self) -> None:
        r = self.client.post(
            reverse("target-list"),
            self._payload(ip=""), format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED, r.content
        assert r.json()["ip"] is None

    def test_create_with_ip_null(self) -> None:
        r = self.client.post(
            reverse("target-list"),
            self._payload(ip=None), format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED, r.content
        assert r.json()["ip"] is None

    def test_explicit_host_overrides_derivation(self) -> None:
        # If the operator does type a host (different from the URL's
        # netloc — useful for IP-based base_url + DNS-style host),
        # the explicit value wins.
        r = self.client.post(
            reverse("target-list"),
            self._payload(host="canonical.example"),
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.json()["host"] == "canonical.example"

    def test_port_stripped_when_deriving_host(self) -> None:
        # base_url with a port → host stored without the port.
        # Matches downstream runners that build their own request URLs
        # from base_url and use `host` for SSL/SNI fingerprinting.
        r = self.client.post(
            reverse("target-list"),
            self._payload(base_url="https://lab.example:8443/"),
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.json()["host"] == "lab.example"

    def test_base_url_still_required(self) -> None:
        # Spec §Validation: base_url is required. Bug-fix scope mustn't
        # accidentally make base_url optional too.
        r = self.client.post(
            reverse("target-list"),
            {"project": str(self.project.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert "base_url" in r.json()
        assert ScanTarget.objects.count() == 0
