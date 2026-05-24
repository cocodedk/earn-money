"""Coverage tests for format_intel_prompt with populated intel data."""
from __future__ import annotations

import pytest
from django.utils import timezone

from apps.agent.target_intel import (
    FormSignature, PriorCandidate, TargetIntel, format_intel_prompt,
)


def _make_intel(**kwargs) -> TargetIntel:
    defaults = dict(
        source_session_id="abc-123",
        source_completed_at=timezone.now(),
        is_stale=False,
    )
    defaults.update(kwargs)
    return TargetIntel(**defaults)


class TestFormatIntelPromptWithRoutes:
    def test_known_routes_appear_sorted(self):
        intel = _make_intel(known_routes={"/b", "/a", "/c"})
        prompt = format_intel_prompt(intel)
        assert "Known routes:" in prompt
        idx_a = prompt.index("  /a")
        idx_b = prompt.index("  /b")
        idx_c = prompt.index("  /c")
        assert idx_a < idx_b < idx_c

    def test_hash_route_in_prompt(self):
        intel = _make_intel(known_routes={"/#!/score-board"})
        prompt = format_intel_prompt(intel)
        assert "/#!/score-board" in prompt


class TestFormatIntelPromptWithForms:
    def test_form_with_named_inputs(self):
        form = FormSignature(action="/login", method="POST", input_names=["email", "pass"])
        intel = _make_intel(form_signatures=[form])
        prompt = format_intel_prompt(intel)
        assert "Forms to re-check:" in prompt
        assert "POST /login inputs: email, pass" in prompt

    def test_form_with_no_inputs_label(self):
        form = FormSignature(action="/search", method="GET", input_names=[])
        intel = _make_intel(form_signatures=[form])
        prompt = format_intel_prompt(intel)
        assert "(no named inputs)" in prompt


class TestFormatIntelPromptWithCandidates:
    def test_candidates_section_rendered(self):
        candidate = PriorCandidate(category="xss", description="Reflected XSS in search")
        intel = _make_intel(prior_candidates=[candidate])
        prompt = format_intel_prompt(intel)
        assert "Prior candidates to re-check:" in prompt
        assert "category: xss" in prompt
        assert "description: Reflected XSS in search" in prompt
        assert "re-verify in current session" in prompt


class TestFormatIntelPromptWithHypotheses:
    def test_hypotheses_section_rendered(self):
        intel = _make_intel(hypotheses=["SQLi in login param", "IDOR on /api/users"])
        prompt = format_intel_prompt(intel)
        assert "Gaps / hypotheses (from prior session" in prompt
        assert '<prior-hypotheses trust="untrusted_prior_session">' in prompt
        assert "- SQLi in login param" in prompt
        assert "- IDOR on /api/users" in prompt
