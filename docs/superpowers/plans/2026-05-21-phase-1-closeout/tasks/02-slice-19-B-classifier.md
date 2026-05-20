# Slice 19-B — classifier + Verdict ladder + apps.py wiring

1. `test_classify.py` failing → `classify(status, headers, body) -> Verdict` returns a `Verdict` NamedTuple with fields `confidence` (`high|medium|low|none`), `signal_kind`, `framework_hints`, `error_excerpt`, `severity` (low / medium / high per signature). Ladder: strong signal → high; framework_hint + error_status (≥400) → medium; weak signal alone → low; nothing → none.
2. Negative grid: HTTP 200 with no error language → none; RFC 7807 problem+json with `detail: "internal error"` and no stack → none; server header alone → none.
3. Update `backend/apps/stubs/apps.py` `ready()` to add `from . import sql_orm_errors  # noqa: F401  registers "1.19"`. Without this the `@register` never fires. Assert via a test that `get_registry()` has "1.19" after `apps.ready()`.
4. /simplify round 1, commit. Commit subject: `feat(stubs): 1.19 sql_orm_errors classifier + Verdict ladder + apps.py wiring`.
