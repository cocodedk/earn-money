"""Tests for RequestBudget."""

from unittest.mock import patch

import pytest

from earn_money.agent.budget import BudgetExceeded, RequestBudget
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType


def _profile(**kwargs: object) -> RoeProfile:
    defaults = dict(
        name="test",
        source_type=RoeSourceType.MANUAL,
        allowed_hosts=["example.com"],
        max_requests=10,
        max_posts=5,
        max_turns=8,
        max_runtime_seconds=60,
        max_response_bytes=100,
        delay_between_requests_ms=0,
    )
    defaults.update(kwargs)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


class TestRequestBudget:
    def test_request_under_limit_allowed(self):
        b = RequestBudget(_profile())
        b.check_request("GET")  # should not raise

    def test_request_over_limit_blocked(self):
        b = RequestBudget(_profile(max_requests=2, max_posts=2))
        b.record_request("GET")
        b.record_request("GET")
        with pytest.raises(BudgetExceeded):
            b.check_request("GET")

    def test_post_over_limit_blocked(self):
        b = RequestBudget(_profile(max_posts=1))
        b.record_request("POST")
        with pytest.raises(BudgetExceeded):
            b.check_request("POST")

    def test_turn_over_limit_blocked(self):
        b = RequestBudget(_profile(max_turns=3))
        with pytest.raises(BudgetExceeded):
            b.check_turn(4)

    def test_turn_at_limit_allowed(self):
        b = RequestBudget(_profile(max_turns=3))
        b.check_turn(3)  # should not raise

    def test_body_is_truncated(self):
        b = RequestBudget(_profile(max_response_bytes=10))
        result = b.truncate_body("hello world this is longer than 10 bytes")
        assert len(result.encode()) <= 10

    def test_body_under_limit_unchanged(self):
        b = RequestBudget(_profile(max_response_bytes=1000))
        body = "short"
        assert b.truncate_body(body) == body

    def test_runtime_limit_blocks_execution(self):
        b = RequestBudget(_profile(max_runtime_seconds=0))
        with pytest.raises(BudgetExceeded):
            b.check_turn(1)

    def test_delay_function_called_when_configured(self):
        b = RequestBudget(_profile(delay_between_requests_ms=10))
        with patch("time.sleep") as mock_sleep:
            b.sleep_if_needed()
            mock_sleep.assert_called_once_with(0.01)

    def test_no_delay_when_zero(self):
        b = RequestBudget(_profile(delay_between_requests_ms=0))
        with patch("time.sleep") as mock_sleep:
            b.sleep_if_needed()
            mock_sleep.assert_not_called()

    def test_record_increments_counters(self):
        b = RequestBudget(_profile())
        b.record_request("GET")
        b.record_request("POST")
        assert b.request_count == 2
        assert b.post_count == 1
