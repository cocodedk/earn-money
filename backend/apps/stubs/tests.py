"""Unit tests for StubRegistry — written BEFORE the registry.

Plain unittest (no DB needed). Uses a tempdir fixture cookbook so tests
are isolated from the real cookbook tree.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from .registry import StubRegistry


STUB_BODY = """---
phase: {phase}
spec: {spec}
slug: {slug}
status: {status}
fixture: {fixture}
---

# {phase}.{spec} {title}

> Phase {phase} — {phase_title} · Category: {category}

## Purpose

Body text for {slug}.
"""


def write_stub(
    cookbook_root: Path,
    *,
    phase: int,
    spec: int,
    phase_slug: str,
    slug: str,
    title: str,
    phase_title: str,
    category: str = "cat",
    status: str = "pending",
    fixture: str = "tbd",
) -> Path:
    phase_dir = cookbook_root / f"{phase:02d}-{phase_slug}"
    phase_dir.mkdir(exist_ok=True)
    spec_path = phase_dir / f"{spec:02d}-{slug}.md"
    spec_path.write_text(
        STUB_BODY.format(
            phase=phase, spec=spec, slug=slug, title=title,
            phase_title=phase_title, category=category,
            status=status, fixture=fixture,
        )
    )
    return spec_path


class StubRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_all_returns_sorted_by_phase_spec(self) -> None:
        write_stub(self.root, phase=1, spec=2, phase_slug="info", slug="server-headers", title="Server headers", phase_title="Information gathering")
        write_stub(self.root, phase=1, spec=1, phase_slug="info", slug="framework-detection", title="Framework detection", phase_title="Information gathering")
        write_stub(self.root, phase=2, spec=1, phase_slug="auth", slug="username-enum", title="Username enum", phase_title="Authentication")
        reg = StubRegistry(self.root)
        rows = reg.all()
        assert [r["slug"] for r in rows] == ["1.1", "1.2", "2.1"]

    def test_get_returns_correct_stub(self) -> None:
        write_stub(self.root, phase=1, spec=1, phase_slug="info", slug="framework-detection", title="Framework detection", phase_title="Information gathering")
        reg = StubRegistry(self.root)
        stub = reg.get("1.1")
        assert stub is not None
        assert stub["title"] == "Framework detection"
        assert stub["phase_title"] == "Information gathering"
        assert stub["category"] == "cat"
        assert stub["status"] == "pending"
        assert stub["fixture"] == "tbd"
        assert stub["spec_slug"] == "framework-detection"
        assert stub["path"] == "01-info/01-framework-detection.md"
        assert "Body text for framework-detection" in stub["body"]

    def test_get_unknown_returns_none(self) -> None:
        reg = StubRegistry(self.root)
        assert reg.get("9.99") is None

    def test_mtime_change_invalidates_cache(self) -> None:
        path = write_stub(self.root, phase=1, spec=1, phase_slug="info", slug="framework-detection", title="Framework detection", phase_title="Information gathering", status="pending")
        reg = StubRegistry(self.root)
        assert reg.get("1.1")["status"] == "pending"
        # Mutate file + bump mtime past 1-second granularity.
        new_text = path.read_text().replace("status: pending", "status: done")
        path.write_text(new_text)
        future = time.time() + 10
        os.utime(path, (future, future))
        assert reg.get("1.1")["status"] == "done"

    def test_removed_file_evicted_from_cache(self) -> None:
        path = write_stub(self.root, phase=1, spec=1, phase_slug="info", slug="framework-detection", title="x", phase_title="y")
        reg = StubRegistry(self.root)
        assert reg.get("1.1") is not None
        path.unlink()
        assert reg.get("1.1") is None

    def test_skips_00_overview(self) -> None:
        phase_dir = self.root / "01-info"
        phase_dir.mkdir()
        (phase_dir / "00-overview.md").write_text("# 1. Info\n\noverview prose\n")
        write_stub(self.root, phase=1, spec=1, phase_slug="info", slug="framework-detection", title="x", phase_title="y")
        reg = StubRegistry(self.root)
        slugs = [r["slug"] for r in reg.all()]
        assert slugs == ["1.1"]

    def test_skips_non_matching_phase_dir(self) -> None:
        (self.root / "not-a-phase").mkdir()
        (self.root / "not-a-phase" / "01-foo.md").write_text("---\nphase: 99\nspec: 99\n---\n\n# 99.99 x\n")
        write_stub(self.root, phase=1, spec=1, phase_slug="info", slug="framework-detection", title="x", phase_title="y")
        reg = StubRegistry(self.root)
        assert [r["slug"] for r in reg.all()] == ["1.1"]

    def test_skips_non_dir_at_cookbook_root(self) -> None:
        """The real cookbook root has files alongside phase dirs
        (README.md, PROGRESS.md, 00-shared-schema.md, …). Registry skips
        them."""
        (self.root / "README.md").write_text("# Cookbook README\n")
        write_stub(self.root, phase=1, spec=1, phase_slug="info", slug="x", title="x", phase_title="y")
        reg = StubRegistry(self.root)
        assert [r["slug"] for r in reg.all()] == ["1.1"]

    def test_skips_glob_match_that_fails_regex(self) -> None:
        """Defense-in-depth: glob `[0-9][0-9]-*.md` matches `01-.md`
        (empty `*`) but SPEC_FILE_RE requires `.+` after the dash."""
        phase_dir = self.root / "01-info"
        phase_dir.mkdir()
        (phase_dir / "01-x.md").write_text(
            "---\nphase: 1\nspec: 1\nslug: x\n---\n\n# 1.1 X\n\n> Phase 1 — y\n"
        )
        (phase_dir / "01-.md").write_text("nothing useful")
        reg = StubRegistry(self.root)
        assert [r["slug"] for r in reg.all()] == ["1.1"]

    def test_skips_files_with_zero_phase_or_spec(self) -> None:
        """Defensive: malformed frontmatter (missing phase/spec)
        produces a stub that the registry refuses."""
        phase_dir = self.root / "01-info"
        phase_dir.mkdir()
        (phase_dir / "01-malformed.md").write_text("---\nphase: 0\nspec: 0\nslug: x\n---\n\n# 0.0 x\n")
        reg = StubRegistry(self.root)
        assert reg.all() == []

    def test_skips_non_spec_filename(self) -> None:
        phase_dir = self.root / "01-info"
        phase_dir.mkdir()
        (phase_dir / "01-framework-detection.md").write_text(
            "---\nphase: 1\nspec: 1\nslug: x\n---\n\n# 1.1 x\n\n> Phase 1 — Info\n"
        )
        (phase_dir / "README.md").write_text("# Info\n")
        reg = StubRegistry(self.root)
        assert [r["slug"] for r in reg.all()] == ["1.1"]

    def test_missing_root_returns_empty(self) -> None:
        reg = StubRegistry(Path(self.tmpdir) / "does-not-exist")
        assert reg.all() == []

    def test_cached_read_skipped_when_mtime_unchanged(self) -> None:
        write_stub(self.root, phase=1, spec=1, phase_slug="info", slug="framework-detection", title="x", phase_title="y")
        reg = StubRegistry(self.root)
        first = reg.get("1.1")
        # Second call: should return the same cached dict.
        assert reg.get("1.1") is first

    def test_blockquote_without_category_parses(self) -> None:
        phase_dir = self.root / "01-info"
        phase_dir.mkdir()
        (phase_dir / "01-x.md").write_text(
            "---\nphase: 1\nspec: 1\nslug: x\n---\n\n# 1.1 X\n\n> Phase 1 — Info gathering\n"
        )
        reg = StubRegistry(self.root)
        stub = reg.get("1.1")
        assert stub["phase_title"] == "Info gathering"
        assert stub["category"] == ""
