"""Tests for /api/health/ — written BEFORE the extension.

Shape promised to agent-em-frontend (2026-05-18):
  {"status": "ok", "db": <bool>, "redis": <bool>,
   "worker": <bool>, "version": <str>}

Each subsystem check is defensive (try/except returning bool) so the
endpoint can never 500 on a broken dependency — it always reports
status=ok with the subsystem bools indicating reality.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def test_returns_all_keys(self) -> None:
        body = self.client.get(reverse("health")).json()
        assert set(body.keys()) == {"status", "db", "redis", "worker", "version"}

    def test_status_is_always_ok(self) -> None:
        body = self.client.get(reverse("health")).json()
        assert body["status"] == "ok"

    def test_version_is_a_string(self) -> None:
        with override_settings(APP_VERSION="test-1.2.3"):
            body = self.client.get(reverse("health")).json()
        assert body["version"] == "test-1.2.3"

    def test_db_true_when_reachable(self) -> None:
        body = self.client.get(reverse("health")).json()
        assert body["db"] is True

    def test_db_false_when_unreachable(self) -> None:
        with patch(
            "config.health.connection.cursor", side_effect=Exception("nope")
        ):
            body = self.client.get(reverse("health")).json()
        assert body["db"] is False

    def test_redis_true_when_pingable(self) -> None:
        with patch("config.health.Redis.from_url") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            body = self.client.get(reverse("health")).json()
        assert body["redis"] is True

    def test_redis_false_when_unreachable(self) -> None:
        with patch(
            "config.health.Redis.from_url",
            side_effect=Exception("connection refused"),
        ):
            body = self.client.get(reverse("health")).json()
        assert body["redis"] is False

    def test_worker_true_when_pingable(self) -> None:
        with patch("config.health._inspect_workers") as mock_inspect:
            mock_inspect.return_value = {"celery@worker1": {"ok": "pong"}}
            body = self.client.get(reverse("health")).json()
        assert body["worker"] is True

    def test_worker_false_when_none_replies(self) -> None:
        with patch("config.health._inspect_workers", return_value=None):
            body = self.client.get(reverse("health")).json()
        assert body["worker"] is False

    def test_worker_false_when_inspect_raises(self) -> None:
        with patch(
            "config.health._inspect_workers", side_effect=Exception("broker down")
        ):
            body = self.client.get(reverse("health")).json()
        assert body["worker"] is False
