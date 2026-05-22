"""Program loader + runtime registry.

Reads `<PROGRAMS_ROOT>/<platform>/<slug>/{scope.md,roe.md}` on demand,
parses YAML frontmatter via `python-frontmatter`, validates the
schema, and caches `Program` objects by `(platform, slug)`. Cache
invalidates on file mtime change so operator edits don't require a
worker restart.

`find_for_host()` resolves a host to exactly one Program:
- exact-literal `in_scope` entry wins over any wildcard;
- otherwise the longest wildcard suffix wins;
- equal-specificity ties raise `AmbiguousProgram`;
- no match raises `OutOfScope`.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter
from django.conf import settings

from .exceptions import AmbiguousProgram, InvalidScope, OutOfScope
from .roe import RoE
from .scope import Policy, Scope, matches_any, normalise_host


_ALLOWED_POLICIES: frozenset[str] = frozenset(
    {"rate-limited-OK", "manual-only", "ambiguous"}
)


@dataclass(frozen=True)
class Program:
    """Resolved runtime view of one `programs/<platform>/<slug>/` dir."""
    platform: str
    slug: str
    scope: Scope
    roe: RoE


def _parse_scope(path: Path, platform: str, slug: str) -> Scope:
    """Parse `scope.md` frontmatter into a Scope dataclass."""
    try:
        post = frontmatter.load(path)
    except Exception as exc:  # malformed YAML, missing file
        raise InvalidScope(f"{path}: {exc}") from exc
    meta: dict[str, Any] = dict(post.metadata)
    policy = meta.get("policy")
    if policy not in _ALLOWED_POLICIES:
        raise InvalidScope(
            f"{path}: unknown policy {policy!r}. Allowed: {sorted(_ALLOWED_POLICIES)}"
        )
    file_platform = str(meta.get("platform") or "")
    file_slug = str(meta.get("slug") or "")
    if file_platform != platform or file_slug != slug:
        raise InvalidScope(
            f"{path}: frontmatter platform/slug ({file_platform!r}/{file_slug!r}) "
            f"does not match path ({platform!r}/{slug!r})"
        )
    in_scope = meta.get("in_scope") or []
    out_of_scope = meta.get("out_of_scope") or []
    if not isinstance(in_scope, list) or not isinstance(out_of_scope, list):
        raise InvalidScope(
            f"{path}: in_scope / out_of_scope must be YAML lists"
        )
    for entry in (*in_scope, *out_of_scope):
        if not isinstance(entry, str) or not entry:
            raise InvalidScope(f"{path}: malformed scope entry {entry!r}")
    return Scope(
        platform=platform, slug=slug, policy=policy,  # type: ignore[arg-type]
        in_scope=list(in_scope), out_of_scope=list(out_of_scope),
        notes=post.content, scope_hash=str(meta.get("scope_hash") or ""),
        last_synced=str(meta.get("last_synced") or ""),
    )


def _parse_roe(path: Path) -> RoE:
    """Parse `roe.md` frontmatter into a RoE dataclass."""
    try:
        post = frontmatter.load(path)
    except Exception as exc:
        raise InvalidScope(f"{path}: {exc}") from exc
    meta: dict[str, Any] = dict(post.metadata)
    rps = meta.get("max_requests_per_second")
    if not isinstance(rps, int) or rps <= 0:
        raise InvalidScope(
            f"{path}: max_requests_per_second must be a positive int, got {rps!r}"
        )
    return RoE(
        max_requests_per_second=rps,
        dos_authorized=bool(meta.get("dos_authorized", False)),
        destructive_payloads_authorized=bool(meta.get("destructive_payloads_authorized", False)),
        social_engineering_authorized=bool(meta.get("social_engineering_authorized", False)),
        pii_handling=str(meta.get("pii_handling") or "one_redacted_screenshot"),
        authorized_test_environments=list(meta.get("authorized_test_environments") or []),
        authorized_test_accounts=list(meta.get("authorized_test_accounts") or []),
        special_notes=str(meta.get("special_notes") or ""),
        # Phase 2 active-probe gates. Default-deny per safety-floor
        # decision — omitted keys stay False.
        allow_active_login_probes=bool(meta.get("allow_active_login_probes", False)),
        allow_password_reset_probes=bool(meta.get("allow_password_reset_probes", False)),
        allow_mfa_probes=bool(meta.get("allow_mfa_probes", False)),
        allow_oauth_probes=bool(meta.get("allow_oauth_probes", False)),
        allow_registration_probes=bool(meta.get("allow_registration_probes", False)),
    )


class ProgramRegistry:
    """Thread-safe Program cache keyed by (platform, slug).

    Each `get()` checks the mtimes of the underlying `scope.md` and
    `roe.md` files; if either changed since the cached read, the
    Program is re-parsed before being returned.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path(root) if root is not None else Path(settings.PROGRAMS_ROOT)
        self._cache: dict[tuple[str, str], tuple[Program, tuple[float, float]]] = {}
        self._lock = threading.Lock()

    def get(self, platform: str, slug: str) -> Program:
        """Return the cached or freshly-parsed Program for the slug.
        Raises `InvalidScope` if either file is missing / malformed."""
        scope_path = self._root / platform / slug / "scope.md"
        roe_path = self._root / platform / slug / "roe.md"
        if not scope_path.is_file() or not roe_path.is_file():
            raise InvalidScope(
                f"missing scope.md or roe.md for {platform}/{slug} "
                f"(root={self._root})"
            )
        mtimes = (scope_path.stat().st_mtime, roe_path.stat().st_mtime)
        with self._lock:
            cached = self._cache.get((platform, slug))
            if cached is not None and cached[1] == mtimes:
                return cached[0]
            program = Program(
                platform=platform, slug=slug,
                scope=_parse_scope(scope_path, platform, slug),
                roe=_parse_roe(roe_path),
            )
            self._cache[(platform, slug)] = (program, mtimes)
            return program

    def all_programs(self) -> list[Program]:
        """Scan PROGRAMS_ROOT for every `<platform>/<slug>/` dir with
        both files and return the loaded Programs."""
        out: list[Program] = []
        if not self._root.is_dir():
            return out
        for platform_dir in sorted(self._root.iterdir()):
            if not platform_dir.is_dir():
                continue
            for slug_dir in sorted(platform_dir.iterdir()):
                if not slug_dir.is_dir():
                    continue
                try:
                    out.append(self.get(platform_dir.name, slug_dir.name))
                except InvalidScope:
                    continue  # skip malformed programs; loader caller can list them
        return out

    def find_for_host(self, host: str) -> Program:
        """Resolve `host` to exactly one Program. See module docstring
        for precedence rules. Raises `OutOfScope` or `AmbiguousProgram`."""
        host = normalise_host(host)
        candidates: list[tuple[Program, str, int]] = []
        for prog in self.all_programs():
            for entry in prog.scope.in_scope:
                entry_l = entry.lower()
                if entry_l == host and not matches_any(host, prog.scope.out_of_scope):
                    # Exact literal — specificity rank 0 (highest).
                    candidates.append((prog, entry_l, 0))
                elif entry_l.startswith("*.") and host.endswith("." + entry_l[2:]):
                    if not matches_any(host, prog.scope.out_of_scope):
                        candidates.append((prog, entry_l, len(entry_l)))
        if not candidates:
            raise OutOfScope(f"host {host!r} not in any program's scope")
        # Primary: exact-literal (rank=0) always beats any wildcard.
        # Secondary: among wildcards, longest suffix wins (-rank).
        candidates.sort(key=lambda c: (0 if c[2] == 0 else 1, -c[2]))
        best_rank = candidates[0][2]
        winners = [c for c in candidates if c[2] == best_rank]
        if len(winners) > 1:
            raise AmbiguousProgram(
                f"host {host!r} matches multiple programs at equal specificity: "
                f"{[w[0].platform + '/' + w[0].slug for w in winners]}"
            )
        return winners[0][0]


_default_registry: ProgramRegistry | None = None
_default_registry_lock = threading.Lock()


def get_registry() -> ProgramRegistry:
    """Return the process-wide default registry (lazy-init from
    settings.PROGRAMS_ROOT)."""
    global _default_registry
    with _default_registry_lock:
        if _default_registry is None:
            _default_registry = ProgramRegistry()
        return _default_registry
