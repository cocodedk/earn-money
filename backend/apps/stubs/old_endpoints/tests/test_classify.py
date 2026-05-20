"""Pure-function tests for stub 1.9 classify_probe."""
from __future__ import annotations

import unittest

from ..classify import classify_probe


def _probe(
    body: str = "",
    status: int = 200,
    location: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    return {
        "status": status,
        "body": body,
        "headers": headers or {},
        "location": location,
    }


class NotFoundTests(unittest.TestCase):
    def test_404_returns_none(self) -> None:
        assert classify_probe("/api/v1", _probe(status=404), "home") is None

    def test_410_returns_none(self) -> None:
        assert classify_probe("/api/v1", _probe(status=410), "home") is None


class ExplicitDeprecationHeaderTests(unittest.TestCase):
    def test_deprecation_yields_confirmed_high(self) -> None:
        verdict = classify_probe(
            "/api/v1",
            _probe(headers={"deprecation": "true"}, body="{}"),
            "home",
        )
        assert verdict is not None
        assert verdict.finding_status == "confirmed"
        assert verdict.confidence == "high"
        assert "header:Deprecation" in verdict.indicators

    def test_header_wins_even_without_path_token(self) -> None:
        # Server says "deprecated" — that's authoritative, regardless
        # of whether the path looks stale.
        verdict = classify_probe(
            "/customers",
            _probe(headers={"sunset": "2025-12-31"}, body="{}"),
            "home",
        )
        assert verdict is not None
        assert verdict.confidence == "high"


class BodyMarkerTests(unittest.TestCase):
    def test_body_marker_yields_confirmed_high(self) -> None:
        verdict = classify_probe(
            "/api/v1",
            _probe(body="<p>This endpoint is deprecated.</p>"),
            "home",
        )
        assert verdict is not None
        assert verdict.finding_status == "confirmed"
        assert verdict.confidence == "high"
        assert "body_marker:deprecation" in verdict.indicators

    def test_body_marker_on_5xx_ignored(self) -> None:
        # Real-world false positive (caught against juiceshop.cocode.dk):
        # Express's default 500 error page echoes the requested path
        # back — e.g. `<title>Error: Unexpected path: /api/deprecated
        # </title>` — and the body marker scan reads "deprecated" as
        # the server confirming the endpoint's deprecation. Spec §5
        # scopes indicator extraction to LIVE responses; gating the
        # body-marker branch on alive status (200/204/206) rejects
        # the echo without losing real deprecated-marker findings.
        verdict = classify_probe(
            "/api/deprecated",
            _probe(
                body="Error: Unexpected path: /api/deprecated",
                status=500,
            ),
            "home",
        )
        assert verdict is None


class StaleTokenLiveTests(unittest.TestCase):
    def test_stale_token_alive_without_marker_candidate_medium(self) -> None:
        verdict = classify_probe(
            "/api/v1", _probe(body='{"users": []}', status=200), "home",
        )
        assert verdict is not None
        assert verdict.finding_status == "candidate"
        assert verdict.confidence == "medium"
        assert verdict.classification == "alive"
        assert "path_token:v1" in verdict.indicators

    def test_baseline_body_match_rejects_candidate(self) -> None:
        # Spec §6: generic_fallback when body matches the homepage —
        # SPA shell / wildcard handler returning the home page for
        # /legacy is NOT an endpoint.
        verdict = classify_probe(
            "/legacy", _probe(body="welcome home", status=200), "welcome home",
        )
        assert verdict is None


class AuthBoundaryTests(unittest.TestCase):
    def test_401_with_stale_token_candidate_medium(self) -> None:
        verdict = classify_probe(
            "/legacy/login", _probe(body="unauthorized", status=401),
            "home",
        )
        assert verdict is not None
        assert verdict.classification == "auth_boundary"
        assert verdict.finding_status == "candidate"
        assert verdict.confidence == "medium"

    def test_403_with_stale_token_candidate_medium(self) -> None:
        verdict = classify_probe(
            "/legacy/admin", _probe(body="forbidden", status=403),
            "home",
        )
        assert verdict is not None
        assert verdict.classification == "auth_boundary"

    def test_401_without_stale_token_yields_none(self) -> None:
        # Random 401 isn't an old endpoint — it's just an auth-gated
        # resource. Need the stale-token signal too.
        verdict = classify_probe(
            "/admin", _probe(body="unauthorized", status=401), "home",
        )
        assert verdict is None


class MethodDiscoveryTests(unittest.TestCase):
    def test_405_with_stale_token_candidate_medium(self) -> None:
        verdict = classify_probe(
            "/legacy/export", _probe(body="", status=405),
            "home",
        )
        assert verdict is not None
        assert verdict.classification == "method_discovery_only"
        assert verdict.finding_status == "candidate"
        assert verdict.confidence == "medium"


class NoStaleSignalTests(unittest.TestCase):
    def test_random_200_without_signal_yields_none(self) -> None:
        # Spec §Negative: "must not create a finding for /products/gold"
        # — a live 200 without ANY stale signal (header, body, path)
        # is just a normal endpoint.
        verdict = classify_probe(
            "/products/gold", _probe(body="<h1>Gold</h1>", status=200),
            "home",
        )
        assert verdict is None

    def test_5xx_yields_none(self) -> None:
        # Spec §Request discipline / §6: error statuses don't prove
        # the endpoint exists in any useful way; must not create a
        # finding from a 500 alone.
        verdict = classify_probe(
            "/api/v1", _probe(body="server error", status=500),
            "home",
        )
        assert verdict is None
