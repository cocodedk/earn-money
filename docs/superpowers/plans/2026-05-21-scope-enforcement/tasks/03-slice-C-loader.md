# Slice C — `loader.py` + `Program` dataclass + `ProgramRegistry`

1. `test_loader.py` failing → `ProgramRegistry.get("hackerone", "algolia")` returns a `Program` with `scope.in_scope == ["www.algolia.com", "*.algolia.net", ...]`, `scope.policy == "rate-limited-OK"`, and `roe.max_requests_per_second == 10`. Cache invalidates on frontmatter mtime change without process restart.
2. Pin the WIRE FORMAT: both `scope.md` and `roe.md` carry YAML frontmatter between `---` fences (exact shape inherited from `archive/v1/programs/hackerone/algolia/{scope.md,roe.md}` — see the AUDIT slice's report for field-by-field). Body markdown below the fences is ignored by the parser. Minimum fields:

   ```yaml
   # scope.md
   platform: hackerone
   slug: algolia
   policy: rate-limited-OK
   in_scope: ["www.algolia.com", "*.algolia.net"]
   out_of_scope: []

   # roe.md
   max_requests_per_second: 10
   dos_authorized: false
   ```

3. `loader.py` parses the frontmatter via `python-frontmatter` (already in `backend/requirements.txt`).
4. `roe.py` — `RoE` dataclass.
5. Settings wiring: add `PROGRAMS_ROOT = Path(os.environ.get("PROGRAMS_ROOT", "/programs"))` to `backend/config/settings.py` (defaults to the container-mount path; local-dev override via env var). Test asserts the loader reads from `settings.PROGRAMS_ROOT`.
6. Policy field acceptance: assert `policy in {"rate-limited-OK", "manual-only", "ambiguous"}`; unknown values raise `InvalidScope`. Slice D's `ManualOnly` raise depends on this parse.
7. Add `ProgramRegistry.find_for_host(host)` for pre-flight: exact match wins over wildcard; otherwise longest wildcard suffix wins; equal-specificity ties raise `AmbiguousProgram`; no match raises `OutOfScope`.
8. Validation rejects missing frontmatter, non-list `in_scope`/`out_of_scope`, non-positive `max_requests_per_second`, malformed wildcard entries, and platform/slug mismatches between path and frontmatter.
9. Commit: `feat(programs): Program loader + RoE dataclass + mtime cache + settings wiring`.
