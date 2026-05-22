"""Contract tests for `apps.programs.loader`.

Coverage matrix per [[plan slice C]]:
- ProgramRegistry.get returns a populated Program for hackerone/algolia
- Cache invalidates on mtime change without process restart
- Policy field acceptance / rejection
- find_for_host: exact > longest-wildcard > AmbiguousProgram > OutOfScope
- Validation: missing frontmatter / non-list scope / non-positive RPS /
  malformed wildcard / platform-slug mismatch
"""
from __future__ import annotations

import textwrap
import time
from pathlib import Path

import pytest
from django.test import override_settings

from apps.programs.exceptions import AmbiguousProgram, InvalidScope, OutOfScope
from apps.programs.loader import Program, ProgramRegistry


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _seed_algolia(root: Path, *, platform: str = "hackerone", slug: str = "algolia") -> None:
    _write(root / platform / slug / "scope.md", f"""
        ---
        platform: {platform}
        slug: {slug}
        policy: rate-limited-OK
        in_scope:
        - www.algolia.com
        - "*.algolia.net"
        out_of_scope: []
        ---
        # body
    """)
    _write(root / platform / slug / "roe.md", """
        ---
        max_requests_per_second: 10
        dos_authorized: false
        ---
    """)


# --- positive shape ---


def test_get_returns_populated_program(tmp_path: Path) -> None:
    _seed_algolia(tmp_path)
    reg = ProgramRegistry(root=tmp_path)
    prog = reg.get("hackerone", "algolia")
    assert isinstance(prog, Program)
    assert prog.scope.in_scope == ["www.algolia.com", "*.algolia.net"]
    assert prog.scope.policy == "rate-limited-OK"
    assert prog.roe.max_requests_per_second == 10
    assert prog.roe.dos_authorized is False


def test_get_uses_settings_root_when_unspecified(tmp_path: Path) -> None:
    _seed_algolia(tmp_path)
    with override_settings(PROGRAMS_ROOT=tmp_path):
        reg = ProgramRegistry()
        assert reg.get("hackerone", "algolia").roe.max_requests_per_second == 10


# --- cache + mtime invalidation ---


def test_get_caches_by_mtime(tmp_path: Path) -> None:
    _seed_algolia(tmp_path)
    reg = ProgramRegistry(root=tmp_path)
    a = reg.get("hackerone", "algolia")
    b = reg.get("hackerone", "algolia")
    assert a is b  # cache hit


def test_cache_invalidates_on_scope_mtime_change(tmp_path: Path) -> None:
    _seed_algolia(tmp_path)
    reg = ProgramRegistry(root=tmp_path)
    a = reg.get("hackerone", "algolia")
    # Mutate scope.md — bump mtime + change a value.
    time.sleep(0.01)
    _write(tmp_path / "hackerone" / "algolia" / "scope.md", """
        ---
        platform: hackerone
        slug: algolia
        policy: rate-limited-OK
        in_scope: ["new.algolia.com"]
        out_of_scope: []
        ---
    """)
    b = reg.get("hackerone", "algolia")
    assert b is not a
    assert b.scope.in_scope == ["new.algolia.com"]


# --- policy / validation rejection ---


@pytest.mark.parametrize("bad_policy", ["unknown", "", "manual"])
def test_unknown_policy_raises(tmp_path: Path, bad_policy: str) -> None:
    _write(tmp_path / "hackerone" / "x" / "scope.md", f"""
        ---
        platform: hackerone
        slug: x
        policy: {bad_policy or '""'}
        in_scope: []
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "x" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(InvalidScope, match="unknown policy"):
        reg.get("hackerone", "x")


def test_missing_files_raise(tmp_path: Path) -> None:
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(InvalidScope, match="missing scope.md or roe.md"):
        reg.get("hackerone", "ghost")


def test_non_list_in_scope_raises(tmp_path: Path) -> None:
    _write(tmp_path / "hackerone" / "x" / "scope.md", """
        ---
        platform: hackerone
        slug: x
        policy: rate-limited-OK
        in_scope: "www.example.com"
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "x" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(InvalidScope, match="must be YAML lists"):
        reg.get("hackerone", "x")


def test_malformed_scope_entry_raises(tmp_path: Path) -> None:
    _write(tmp_path / "hackerone" / "x" / "scope.md", """
        ---
        platform: hackerone
        slug: x
        policy: rate-limited-OK
        in_scope: [""]
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "x" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(InvalidScope, match="malformed scope entry"):
        reg.get("hackerone", "x")


def test_platform_slug_mismatch_raises(tmp_path: Path) -> None:
    _write(tmp_path / "hackerone" / "x" / "scope.md", """
        ---
        platform: bugcrowd
        slug: x
        policy: rate-limited-OK
        in_scope: []
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "x" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(InvalidScope, match="does not match path"):
        reg.get("hackerone", "x")


@pytest.mark.parametrize("bad_rps", [0, -1, "abc"])
def test_non_positive_rps_raises(tmp_path: Path, bad_rps: object) -> None:
    _write(tmp_path / "hackerone" / "x" / "scope.md", """
        ---
        platform: hackerone
        slug: x
        policy: rate-limited-OK
        in_scope: []
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "x" / "roe.md", f"""
        ---
        max_requests_per_second: {bad_rps}
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(InvalidScope, match="max_requests_per_second"):
        reg.get("hackerone", "x")


# --- find_for_host ---


def test_find_for_host_exact_match(tmp_path: Path) -> None:
    _seed_algolia(tmp_path)
    reg = ProgramRegistry(root=tmp_path)
    prog = reg.find_for_host("www.algolia.com")
    assert prog.slug == "algolia"


def test_find_for_host_wildcard_match(tmp_path: Path) -> None:
    _seed_algolia(tmp_path)
    reg = ProgramRegistry(root=tmp_path)
    prog = reg.find_for_host("dashboard.algolia.net")
    assert prog.slug == "algolia"


def test_find_for_host_no_match_raises_out_of_scope(tmp_path: Path) -> None:
    _seed_algolia(tmp_path)
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(OutOfScope):
        reg.find_for_host("evil.example.com")


def test_find_for_host_exact_beats_wildcard(tmp_path: Path) -> None:
    """Two programs both 'cover' the host: program A via exact literal,
    program B via wildcard. Exact wins."""
    _write(tmp_path / "hackerone" / "exact-prog" / "scope.md", """
        ---
        platform: hackerone
        slug: exact-prog
        policy: rate-limited-OK
        in_scope: ["api.shared.com"]
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "exact-prog" / "roe.md", """
        ---
        max_requests_per_second: 5
        ---
    """)
    _write(tmp_path / "hackerone" / "wildcard-prog" / "scope.md", """
        ---
        platform: hackerone
        slug: wildcard-prog
        policy: rate-limited-OK
        in_scope: ["*.shared.com"]
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "wildcard-prog" / "roe.md", """
        ---
        max_requests_per_second: 5
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    assert reg.find_for_host("api.shared.com").slug == "exact-prog"


def test_find_for_host_longest_wildcard_wins(tmp_path: Path) -> None:
    _write(tmp_path / "hackerone" / "broad" / "scope.md", """
        ---
        platform: hackerone
        slug: broad
        policy: rate-limited-OK
        in_scope: ["*.shared.com"]
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "broad" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    _write(tmp_path / "hackerone" / "narrow" / "scope.md", """
        ---
        platform: hackerone
        slug: narrow
        policy: rate-limited-OK
        in_scope: ["*.api.shared.com"]
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "narrow" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    assert reg.find_for_host("v2.api.shared.com").slug == "narrow"


def test_find_for_host_ambiguous_raises(tmp_path: Path) -> None:
    _write(tmp_path / "hackerone" / "a" / "scope.md", """
        ---
        platform: hackerone
        slug: a
        policy: rate-limited-OK
        in_scope: ["*.shared.com"]
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "a" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    _write(tmp_path / "hackerone" / "b" / "scope.md", """
        ---
        platform: hackerone
        slug: b
        policy: rate-limited-OK
        in_scope: ["*.shared.com"]
        out_of_scope: []
        ---
    """)
    _write(tmp_path / "hackerone" / "b" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(AmbiguousProgram, match="matches multiple programs"):
        reg.find_for_host("x.shared.com")


def test_find_for_host_respects_out_of_scope(tmp_path: Path) -> None:
    _write(tmp_path / "hackerone" / "a" / "scope.md", """
        ---
        platform: hackerone
        slug: a
        policy: rate-limited-OK
        in_scope: ["*.example.com"]
        out_of_scope: ["blocked.example.com"]
        ---
    """)
    _write(tmp_path / "hackerone" / "a" / "roe.md", """
        ---
        max_requests_per_second: 1
        ---
    """)
    reg = ProgramRegistry(root=tmp_path)
    # Allowed via wildcard:
    assert reg.find_for_host("allowed.example.com").slug == "a"
    # Blocked despite wildcard:
    with pytest.raises(OutOfScope):
        reg.find_for_host("blocked.example.com")


# --- registry sweep ---


def test_all_programs_skips_malformed(tmp_path: Path) -> None:
    _seed_algolia(tmp_path)
    # Add a broken sibling.
    (tmp_path / "hackerone" / "broken").mkdir()
    (tmp_path / "hackerone" / "broken" / "scope.md").write_text("bad", encoding="utf-8")
    reg = ProgramRegistry(root=tmp_path)
    progs = reg.all_programs()
    slugs = [p.slug for p in progs]
    assert slugs == ["algolia"]


def test_all_programs_empty_when_root_missing(tmp_path: Path) -> None:
    reg = ProgramRegistry(root=tmp_path / "nope")
    assert reg.all_programs() == []


def test_all_programs_skips_non_directories(tmp_path: Path) -> None:
    """Stray files at PROGRAMS_ROOT or under a platform dir are
    ignored, not parsed."""
    _seed_algolia(tmp_path)
    (tmp_path / "stray.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "hackerone" / "stray.txt").write_text("hi", encoding="utf-8")
    reg = ProgramRegistry(root=tmp_path)
    progs = reg.all_programs()
    assert [p.slug for p in progs] == ["algolia"]


def test_malformed_yaml_in_scope_raises(tmp_path: Path) -> None:
    """Broken YAML frontmatter is caught by `_parse_scope` and wrapped
    in `InvalidScope` so callers can catch one type."""
    (tmp_path / "hackerone" / "x").mkdir(parents=True)
    (tmp_path / "hackerone" / "x" / "scope.md").write_text(
        "---\nplatform: [unclosed\n---\n", encoding="utf-8",
    )
    (tmp_path / "hackerone" / "x" / "roe.md").write_text(
        "---\nmax_requests_per_second: 1\n---\n", encoding="utf-8",
    )
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(InvalidScope):
        reg.get("hackerone", "x")


def test_malformed_yaml_in_roe_raises(tmp_path: Path) -> None:
    _write(tmp_path / "hackerone" / "x" / "scope.md", """
        ---
        platform: hackerone
        slug: x
        policy: rate-limited-OK
        in_scope: []
        out_of_scope: []
        ---
    """)
    (tmp_path / "hackerone" / "x" / "roe.md").write_text(
        "---\nmax_requests_per_second: [bad\n---\n", encoding="utf-8",
    )
    reg = ProgramRegistry(root=tmp_path)
    with pytest.raises(InvalidScope):
        reg.get("hackerone", "x")


def test_get_registry_returns_singleton() -> None:
    """`get_registry()` lazy-initialises once and reuses."""
    from apps.programs import loader
    loader._default_registry = None
    a = loader.get_registry()
    b = loader.get_registry()
    assert a is b
    loader._default_registry = None  # cleanup
