# Slice 19-AUDIT — spec audit BEFORE implementation

Read `19-sql-orm-errors.md` end-to-end FIRST, before any code lands. Audit informs the implementation shape; finding spec drift after code is set is too late (codex Stage 5 finding 2026-05-20).

1. Read the spec sections: Purpose, Inputs, Detection logic, Persistence, Pass/fail assertions (including negative assertions), Acceptance criteria.
2. Extract every typed shape the spec mandates: `Signature` fields, `Verdict` fields, `Finding.data` keys (including `disclosed_schema_terms[]` per spec §typed-finding-shape), confidence vocabulary, status vocabulary, severity hints.
3. Verify shared types (`ScanTarget`, `Evidence`) are sufficient. If the spec needs a new shared type, surface it BEFORE implementation — pre-empts mid-stack rewrites.
4. Write audit report at `docs/superpowers/spec-reviews/2026-05-21-stub-1.19-sql-orm-errors-pre.md` listing every mandated field + every "must not" rule.
5. Commit. Commit subject: `docs(stub-reviews): 1.19 sql_orm_errors pre-implementation spec audit`.
