"""StubRegistry — file-backed cache over the cookbook tree.

Parses YAML frontmatter from every `<phase>/<spec>.md` under the
cookbook root. Caches the parsed dict per-slug; invalidates an entry
when its backing file's mtime changes. Adds new files automatically on
the next `all()` call; removes stubs whose files disappeared.

Slug format is `<phase>.<spec>` from the YAML frontmatter (e.g. "1.1",
"24.9"). The cookbook's own `slug:` (kebab-case) is exposed separately
as `spec_slug`.

Thread-safe via a single lock around `_refresh`.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

import frontmatter
from django.conf import settings


PHASE_DIR_RE = re.compile(r"^(\d{2})-(.+)$")
SPEC_FILE_RE = re.compile(r"^(\d{2})-(.+)\.md$")
TITLE_RE = re.compile(r"^# (\d+)\.(\d+)\s+(.+)$", re.MULTILINE)
BLOCKQUOTE_RE = re.compile(
    r"^> Phase (\d+) — ([^·\n]+?)(?: · Category: ([^\n]+?))?\s*$",
    re.MULTILINE,
)


class StubRegistry:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._cache: dict[str, dict[str, Any]] = {}
        self._mtimes: dict[str, float] = {}
        self._lock = threading.Lock()

    def all(self) -> list[dict[str, Any]]:
        self._refresh()
        return sorted(
            self._cache.values(), key=lambda s: (s["phase"], s["spec"])
        )

    def get(self, slug: str) -> dict[str, Any] | None:
        self._refresh()
        return self._cache.get(slug)

    def _refresh(self) -> None:
        with self._lock:
            seen: set[str] = set()
            if not self._root.exists():
                self._cache.clear()
                self._mtimes.clear()
                return
            for phase_dir in sorted(self._root.iterdir()):
                if not phase_dir.is_dir():
                    continue
                if not PHASE_DIR_RE.match(phase_dir.name):
                    continue
                for spec_path in sorted(phase_dir.glob("[0-9][0-9]-*.md")):
                    if spec_path.name == "00-overview.md":
                        continue
                    if not SPEC_FILE_RE.match(spec_path.name):
                        continue
                    slug = self._ingest(phase_dir, spec_path)
                    if slug is not None:
                        seen.add(slug)
            stale = set(self._cache.keys()) - seen
            for slug in stale:
                del self._cache[slug]
                del self._mtimes[slug]

    def _ingest(self, phase_dir: Path, spec_path: Path) -> str | None:
        text = spec_path.read_text(encoding="utf-8")
        try:
            fm = frontmatter.loads(text)
        except Exception:  # pragma: no cover — malformed YAML on disk
            return None
        phase = int(fm.get("phase", 0))
        spec_num = int(fm.get("spec", 0))
        if phase <= 0 or spec_num <= 0:
            return None
        slug = f"{phase}.{spec_num}"
        mtime = spec_path.stat().st_mtime
        if self._mtimes.get(slug) == mtime and slug in self._cache:
            return slug
        body = fm.content
        title_m = TITLE_RE.search(body)
        title = title_m.group(3).strip() if title_m else slug
        bq_m = BLOCKQUOTE_RE.search(body)
        phase_title = bq_m.group(2).strip() if bq_m else ""
        category = bq_m.group(3).strip() if bq_m and bq_m.group(3) else ""
        self._cache[slug] = {
            "slug": slug,
            "phase": phase,
            "spec": spec_num,
            "phase_slug": phase_dir.name,
            "spec_slug": str(fm.get("slug", "")),
            "title": title,
            "phase_title": phase_title,
            "category": category,
            "status": str(fm.get("status", "pending")),
            "fixture": str(fm.get("fixture", "tbd")),
            "path": f"{phase_dir.name}/{spec_path.name}",
            "body": body,
        }
        self._mtimes[slug] = mtime
        return slug


_registries: dict[str, StubRegistry] = {}
_registries_lock = threading.Lock()


def get_registry() -> StubRegistry:
    """Return a process-wide registry for the configured cookbook root.

    Keyed by path so tests using `override_settings(COOKBOOK_ROOT=...)`
    get a fresh registry per tmpdir without polluting the default one.
    """
    root = str(settings.COOKBOOK_ROOT)
    with _registries_lock:
        if root not in _registries:
            _registries[root] = StubRegistry(Path(root))
        return _registries[root]
