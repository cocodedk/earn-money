"""Tests for HttpTool."""

from unittest.mock import MagicMock, patch

import pytest

from earn_money.agent.budget import BudgetExceeded, RequestBudget
from earn_money.agent.http_tool import HttpTool
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType
from earn_money.agent.scope_policy import ScopeDenied, ScopePolicy


def _profile(**kwargs: object) -> RoeProfile:
    defaults = dict(
        name="test",
        source_type=RoeSourceType.MANUAL,
        allowed_hosts=["target.example.com"],
        max_requests=100,
        max_posts=20,
        max_turns=25,
        max_runtime_seconds=180,
        max_response_bytes=5000,
        delay_between_requests_ms=0,
        allow_get=True,
        allow_post=True,
    )
    defaults.update(kwargs)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


def _tool(**kwargs: object) -> HttpTool:
    profile = _profile(**kwargs)
    roe_policy = RoePolicy(profile)
    scope_policy = ScopePolicy(profile, "https://target.example.com")
    budget = RequestBudget(profile)
    return HttpTool("https://target.example.com", roe_policy, scope_policy, budget)


def _mock_response(
    status: int = 200, text: str = "ok", headers: dict | None = None, is_redirect: bool = False
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.headers = headers or {"content-type": "application/json"}
    resp.url = MagicMock()
    resp.url.__str__ = lambda s: "https://target.example.com/api"
    resp.is_redirect = is_redirect
    return resp


class TestHttpTool:
    def test_get_returns_observation_wrapper(self):
        tool = _tool()
        with patch("httpx.Client") as mock_cls:
            mock_client = mock_cls.return_value.__enter__.return_value
            mock_client.request.return_value = _mock_response()
            result = tool.get("/api/users")
        assert isinstance(result, ObservationWrapper)

    def test_post_sends_json_body_returns_observation_wrapper(self):
        tool = _tool()
        with patch("httpx.Client") as mock_cls:
            mock_client = mock_cls.return_value.__enter__.return_value
            mock_client.request.return_value = _mock_response()
            result = tool.post("/login", json_body={"email": "a@b.com"})
        assert isinstance(result, ObservationWrapper)

    def test_header_persists_across_calls(self):
        tool = _tool()
        tool.set_header("Authorization", "Bearer tok")
        assert tool.session_headers["Authorization"] == "Bearer tok"

    def test_unsupported_header_is_rejected(self):
        tool = _tool()
        with pytest.raises(ValueError):
            tool.set_header("X-Evil-Header", "bad")

    def test_external_url_is_rejected(self):
        tool = _tool()
        with pytest.raises((ScopeDenied, PermissionError)), patch("httpx.Client"):
            tool.get("https://evil.com/steal")

    def test_roe_denied_post_is_rejected(self):
        tool = _tool(allow_post=False)
        with pytest.raises(PermissionError):
            tool.post("/login", json_body={})

    def test_request_over_budget_is_rejected(self):
        tool = _tool(max_requests=0, max_posts=0)
        with pytest.raises(BudgetExceeded), patch("httpx.Client"):
            tool.get("/api")

    def test_response_body_is_truncated(self):
        tool = _tool(max_response_bytes=5)
        with patch("httpx.Client") as mock_cls:
            mock_client = mock_cls.return_value.__enter__.return_value
            mock_client.request.return_value = _mock_response(text="hello world this is long")
            result = tool.get("/api/users")
        assert len(result.body.encode()) <= 5

    def test_request_count_is_recorded(self):
        tool = _tool()
        with patch("httpx.Client") as mock_cls:
            mock_client = mock_cls.return_value.__enter__.return_value
            mock_client.request.return_value = _mock_response()
            tool.get("/api/users")
        assert tool.budget.request_count == 1

    def test_post_count_is_recorded(self):
        tool = _tool()
        with patch("httpx.Client") as mock_cls:
            mock_client = mock_cls.return_value.__enter__.return_value
            mock_client.request.return_value = _mock_response()
            tool.post("/login", json_body={})
        assert tool.budget.post_count == 1

    def test_jwt_decode_returns_header_and_payload(self):
        import base64
        import json as _json

        alg = base64.urlsafe_b64encode(_json.dumps({"alg": "HS256"}).encode()).rstrip(b"=").decode()
        sub = base64.urlsafe_b64encode(_json.dumps({"sub": "1"}).encode()).rstrip(b"=").decode()
        header, payload = alg, sub
        token = f"{header}.{payload}.sig"
        tool = _tool()
        h, p = tool.decode_jwt(token)
        assert h["alg"] == "HS256"
        assert p["sub"] == "1"

    def test_invalid_jwt_raises_clean_error(self):
        tool = _tool()
        with pytest.raises(ValueError):
            tool.decode_jwt("not.a.jwt.at.all.extra")

    def test_observation_wrapper_has_correct_fields(self):
        tool = _tool()
        with patch("httpx.Client") as mock_cls:
            mock_client = mock_cls.return_value.__enter__.return_value
            mock_client.request.return_value = _mock_response(status=201, text="created")
            result = tool.get("/api/items")
        assert result.status == 201
        assert result.body == "created"
        assert "UNTRUSTED TARGET CONTENT" in result.warning
