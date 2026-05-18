"""Tests for FindingVerifier."""


from earn_money.agent.finding_verifier import FindingVerifier
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType


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
        allow_idor_checks=True,
        require_replay_steps=True,
    )
    defaults.update(kwargs)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


def _obs(status: int = 200, body: str = "", headers: dict | None = None) -> ObservationWrapper:
    return ObservationWrapper.from_response(
        status=status,
        final_url="https://target.example.com/api",
        all_headers=headers or {},
        body=body,
    )


def _action(path: str, tool: str = "get") -> dict:
    return {"tool": tool, "category": "http_get", "args": {"path": path}}


class TestFindingVerifier:
    def test_idor_candidate_created(self):
        v = FindingVerifier(_profile())
        session = HackerSession()
        obs = _obs(body='{"email":"a@b.com","user_id":999}')
        candidates, verified = v.evaluate(_action("/api/users/999"), obs, session)
        assert any(f["type"] == "idor" for f in candidates)
        assert verified == []

    def test_idor_not_created_for_non_numeric_path(self):
        v = FindingVerifier(_profile())
        obs = _obs(body='{"email":"a@b.com"}')
        c, _ = v.evaluate(_action("/api/users/me"), obs, HackerSession())
        assert not any(f["type"] == "idor" for f in c)

    def test_idor_not_created_for_non_200(self):
        v = FindingVerifier(_profile())
        obs = _obs(status=403, body='{"email":"a@b.com","user_id":999}')
        c, _ = v.evaluate(_action("/api/users/999"), obs, HackerSession())
        assert not any(f["type"] == "idor" for f in c)

    def test_idor_promoted_with_active_user_and_roe(self):
        v = FindingVerifier(_profile(allow_idor_checks=True))
        session = HackerSession()
        session.store_id("user_id", "1")  # active user is 1
        obs = _obs(body='{"email":"victim@b.com","user_id":999}')
        _, verified = v.evaluate(_action("/api/users/999"), obs, session)
        assert any(f["type"] == "idor" and f["confirmed"] for f in verified)

    def test_idor_not_promoted_without_roe(self):
        v = FindingVerifier(_profile(allow_idor_checks=False))
        session = HackerSession()
        session.store_id("user_id", "1")
        obs = _obs(body='{"email":"victim@b.com","user_id":999}')
        _, verified = v.evaluate(_action("/api/users/999"), obs, session)
        assert verified == []

    def test_debug_endpoint_candidate_created(self):
        v = FindingVerifier(_profile())
        obs = _obs(body="JAVA_HOME=/usr/bin/java DB_PASSWORD=secret")
        c, _ = v.evaluate(_action("/actuator/env"), obs, HackerSession())
        assert any(f["type"] == "debug_endpoint" for f in c)

    def test_token_leak_candidate_masks_token(self):
        v = FindingVerifier(_profile())
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig"
        obs = _obs(body=f'{{"token":"{jwt}"}}')
        c, _ = v.evaluate(_action("/api/token"), obs, HackerSession())
        token_finds = [f for f in c if f["type"] == "token_leak"]
        assert token_finds
        for masked in token_finds[0]["tokens_masked"]:
            assert jwt not in masked
            assert "***" in masked

    def test_unsafe_redirect_candidate_created(self):
        v = FindingVerifier(_profile())
        obs = _obs(body="", headers={"location": "https://attacker.com/steal"})
        c, _ = v.evaluate(_action("/login?next=https://attacker.com/steal"), obs, HackerSession())
        assert any(f["type"] == "unsafe_redirect" for f in c)

    def test_candidate_not_promoted_without_replay_steps(self):
        v = FindingVerifier(_profile(require_replay_steps=True, allow_idor_checks=True))
        session = HackerSession()
        # No active user_id stored → can't produce replay → stays as candidate
        obs = _obs(body='{"email":"victim@b.com","user_id":999}')
        c, verified = v.evaluate(_action("/api/users/999"), obs, session)
        assert verified == []
        assert any(f["type"] == "idor" for f in c)

    def test_verified_finding_includes_replay_steps(self):
        v = FindingVerifier(_profile(allow_idor_checks=True))
        session = HackerSession()
        session.store_id("user_id", "1")
        obs = _obs(body='{"email":"victim@b.com","user_id":999}')
        _, verified = v.evaluate(_action("/api/users/999"), obs, session)
        assert verified and "replay" in verified[0]
