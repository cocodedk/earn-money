"""Tests for HackerSession."""

from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.observations import ObservationWrapper


def _obs(body: str = "body") -> ObservationWrapper:
    return ObservationWrapper.from_response(200, "https://example.com", {}, body)


class TestHackerSession:
    def test_token_storage(self):
        s = HackerSession()
        s.store_token("access", "tok123")
        assert s.get_token("access") == "tok123"

    def test_token_names_only_in_prompt_view(self):
        s = HackerSession()
        s.store_token("access", "super-secret-value")
        view = s.prompt_view()
        assert "access" in view
        assert "super-secret-value" not in view

    def test_id_storage(self):
        s = HackerSession()
        s.store_id("user_id", "42")
        assert s.ids["user_id"] == "42"

    def test_url_dedupe(self):
        s = HackerSession()
        s.seed_urls(["https://a.com", "https://b.com", "https://a.com"])
        assert s.urls.count("https://a.com") == 1
        assert len(s.urls) == 2

    def test_observation_storage(self):
        s = HackerSession()
        obs = _obs("response body")
        s.add_observation(obs)
        assert obs in s.observations

    def test_hypothesis_storage(self):
        s = HackerSession()
        s.add_hypothesis("IDOR possible at /api/users/{id}")
        assert len(s.hypotheses) == 1

    def test_candidate_finding_storage(self):
        s = HackerSession()
        s.add_candidate_finding({"type": "idor", "url": "/api/users/999"})
        assert len(s.candidate_findings) == 1

    def test_verified_finding_storage(self):
        s = HackerSession()
        s.add_verified_finding({"type": "idor", "confirmed": True})
        assert len(s.verified_findings) == 1

    def test_policy_denial_storage(self):
        s = HackerSession()
        s.add_policy_denial("brute force not allowed by RoE")
        assert "brute force not allowed by RoE" in s.policy_denials

    def test_turn_logging(self):
        s = HackerSession()
        s.log_turn({"tool": "get"}, "completed")
        assert len(s.turn_log) == 1

    def test_summary_counts(self):
        s = HackerSession()
        s.store_token("a", "v")
        s.store_id("uid", "1")
        s.seed_urls(["https://x.com"])
        s.add_observation(_obs())
        s.add_candidate_finding({})
        s.add_verified_finding({})
        s.log_turn({}, "done")
        summary = s.summary()
        assert summary["tokens"] == 1
        assert summary["ids"] == 1
        assert summary["urls"] == 1
        assert summary["observations"] == 1
        assert summary["candidate_findings"] == 1
        assert summary["verified_findings"] == 1
        assert summary["turns"] == 1
