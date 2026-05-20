# Slice A — `apps/programs/` app skeleton + `Scope` dataclass + wildcard matcher

1. `test_scope.py` failing → `matches_scope("dashboard.algolia.net", in_scope=["*.algolia.net"], out_of_scope=[]) is True`. Coverage matrix: exact / wildcard / wildcard does not match bare apex / out-of-scope override / port-agnostic / case-insensitive / trailing-dot strip / IDNA normalization / malformed host rejects closed.
2. Create `apps/programs/` Django app (apps.py, registered in INSTALLED_APPS).
3. `scope.py` — `Scope` dataclass + `matches_scope()` per archived v1 implementation. `matches_scope()` accepts a host-like string only; URL parsing stays in scan pre-flight and `scope_check.enforce_scope`.
4. Define `InvalidScope` / `OutOfScope` in the shared exceptions module so later slices import one exception type instead of creating local copies.
5. Commit: `feat(programs): Scope dataclass + wildcard hostname matcher`.
