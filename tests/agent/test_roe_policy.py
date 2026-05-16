"""Tests for RoE policy engine."""


from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType


def _profile(**kwargs: object) -> RoeProfile:
    defaults = dict(
        name="test",
        source_type=RoeSourceType.MANUAL,
        allowed_hosts=["example.com"],
        max_requests=100,
        max_posts=20,
        max_turns=25,
        max_runtime_seconds=180,
        max_response_bytes=12000,
        delay_between_requests_ms=500,
    )
    defaults.update(kwargs)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


class TestRoePolicy:
    def test_get_allowed_when_profile_allows(self):
        policy = RoePolicy(_profile(allow_get=True))
        d = policy.decide("http_get")
        assert d.allowed is True

    def test_get_denied_when_profile_disallows(self):
        policy = RoePolicy(_profile(allow_get=False))
        d = policy.decide("http_get")
        assert d.allowed is False

    def test_post_denied_when_profile_disables(self):
        policy = RoePolicy(_profile(allow_post=False))
        d = policy.decide("http_post")
        assert d.allowed is False
        assert "POST" in d.reason

    def test_post_allowed_when_profile_enables(self):
        policy = RoePolicy(_profile(allow_post=True))
        d = policy.decide("http_post")
        assert d.allowed is True

    def test_rate_limit_denied_unless_enabled(self):
        policy = RoePolicy(_profile(allow_rate_limit_testing=False))
        d = policy.decide("rate_limit_test")
        assert d.allowed is False

    def test_rate_limit_allowed_when_enabled(self):
        policy = RoePolicy(_profile(allow_rate_limit_testing=True))
        d = policy.decide("rate_limit_test")
        assert d.allowed is True

    def test_bruteforce_denied_unless_enabled(self):
        policy = RoePolicy(_profile(allow_bruteforce=False))
        d = policy.decide("bruteforce")
        assert d.allowed is False

    def test_bruteforce_allowed_when_enabled(self):
        policy = RoePolicy(_profile(allow_bruteforce=True))
        d = policy.decide("bruteforce")
        assert d.allowed is True

    def test_exploit_chain_denied_unless_enabled(self):
        policy = RoePolicy(_profile(allow_exploit_chains=False))
        d = policy.decide("exploit_chain")
        assert d.allowed is False

    def test_exploit_chain_allowed_when_enabled(self):
        policy = RoePolicy(_profile(allow_exploit_chains=True))
        d = policy.decide("exploit_chain")
        assert d.allowed is True

    def test_destructive_denied_unless_enabled(self):
        policy = RoePolicy(_profile(allow_destructive_actions=False))
        d = policy.decide("destructive")
        assert d.allowed is False

    def test_idor_check_allowed_only_when_enabled(self):
        policy_off = RoePolicy(_profile(allow_idor_checks=False))
        policy_on = RoePolicy(_profile(allow_idor_checks=True))
        assert policy_off.decide("idor_check").allowed is False
        assert policy_on.decide("idor_check").allowed is True

    def test_graphql_introspection_allowed_only_when_enabled(self):
        policy_off = RoePolicy(_profile(allow_graphql_introspection=False))
        policy_on = RoePolicy(_profile(allow_graphql_introspection=True))
        assert policy_off.decide("graphql_introspection").allowed is False
        assert policy_on.decide("graphql_introspection").allowed is True

    def test_unknown_category_denied(self):
        policy = RoePolicy(_profile())
        d = policy.decide("launch_missiles")
        assert d.allowed is False

    def test_denial_reason_is_readable(self):
        policy = RoePolicy(_profile(allow_bruteforce=False))
        d = policy.decide("bruteforce")
        assert len(d.reason) > 5

    def test_always_allowed_categories(self):
        policy = RoePolicy(_profile())
        for cat in ("recon", "report_candidate", "store_memory", "stop"):
            assert policy.decide(cat).allowed is True
