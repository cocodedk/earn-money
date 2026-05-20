# Slice 19-A — `sql_orm_errors` signatures + matcher

Stack: `feat/em-backend-1.19-sql-orm-errors` (one branch per stub per [[project-stacked-branch-convention]]). Pre-requisite: [`00-slice-19-AUDIT-spec-review-first.md`](00-slice-19-AUDIT-spec-review-first.md) committed first.

1. `test_signatures.py` failing → assert each DB/ORM family has a typed `Signature` row with non-empty regex + named groups for `table`, `column`, `query_fragment`, `path` where present. Severity hints per family land here (medium default; high if SQL fragment + table name both extractable).
2. `signals.py`: `find_strongest_signal(body: bytes) -> Optional[Match]` returns the highest-priority match, or `None`. Tests cover one positive + one negative per family (PostgreSQL / MySQL / MSSQL / Oracle / SQLite / Django ORM / SQLAlchemy / Hibernate / ActiveRecord / Sequel / MongoDB).
3. /simplify round 1, commit. Commit subject: `feat(stubs): 1.19 sql_orm_errors signatures + matcher`.
