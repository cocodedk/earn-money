"""Contract tests for the `RoE` dataclass fields.

The Phase 2 active-probe gates are NEW boolean fields; this test
suite locks in the defaults + the load-through-roe.md path so a
future schema change can't silently re-enable active probing on
existing programs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.programs.loader import ProgramRegistry
from apps.programs.roe import RoE


PHASE_2_GATES = (
    "allow_active_login_probes",
    "allow_password_reset_probes",
    "allow_mfa_probes",
    "allow_oauth_probes",
    "allow_registration_probes",
)


@pytest.mark.parametrize("field_name", PHASE_2_GATES)
def test_phase_2_gate_defaults_to_false(field_name: str) -> None:
    """Every Phase 2 active-probe knob defaults to False — default-deny
    is the safety floor."""
    roe = RoE(max_requests_per_second=10)
    assert getattr(roe, field_name) is False


def test_existing_floor_fields_still_default_to_safe_values() -> None:
    """The Phase 1 floor must remain unchanged when Phase 2 knobs land."""
    roe = RoE(max_requests_per_second=5)
    assert roe.dos_authorized is False
    assert roe.destructive_payloads_authorized is False
    assert roe.social_engineering_authorized is False


@pytest.mark.parametrize("field_name", PHASE_2_GATES)
def test_phase_2_gate_can_be_set_true(field_name: str) -> None:
    """Each new knob accepts True without unfreezing the rest of the
    dataclass — explicit per-flow opt-in works."""
    roe = RoE(max_requests_per_second=10, **{field_name: True})
    assert getattr(roe, field_name) is True


@pytest.mark.parametrize("field_name", PHASE_2_GATES)
def test_phase_2_gate_loads_from_roe_md(
    tmp_path: Path, field_name: str,
) -> None:
    """A program whose roe.md explicitly sets a Phase 2 knob to true
    parses with that field True via the loader. Other knobs stay
    False — no implicit cross-contamination."""
    program_dir = tmp_path / "hackerone" / "fixture"
    program_dir.mkdir(parents=True)
    (program_dir / "scope.md").write_text(
        "---\n"
        "platform: hackerone\n"
        "slug: fixture\n"
        "policy: rate-limited-OK\n"
        "in_scope:\n"
        "  - example.test\n"
        "out_of_scope: []\n"
        "---\n# fixture\n"
    )
    (program_dir / "roe.md").write_text(
        "---\n"
        "max_requests_per_second: 10\n"
        f"{field_name}: true\n"
        "---\n# fixture roe\n"
    )

    registry = ProgramRegistry(root=tmp_path)
    program = registry.find_for_host("example.test")
    assert getattr(program.roe, field_name) is True
    for other in PHASE_2_GATES:
        if other == field_name:
            continue
        assert getattr(program.roe, other) is False, (
            f"setting {field_name}=true must not flip {other}"
        )
