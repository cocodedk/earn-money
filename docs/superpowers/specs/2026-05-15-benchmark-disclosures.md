# Disclosure-replay benchmark — design notes

> Operational record for the benchmark feature shipped 2026-05-15. Captures the storage-scope decision and the column-set rationale so Phase B inherits the right assumptions.

## Storage scope decision: per-program SQLite

Per-program `db.sqlite` holds the `benchmark_disclosures` table, alongside `signals` / `findings` / `recon_runs` for that program. Decision recorded after coordinator's cursor-agent review surfaced the alternative (a shared benchmark DB keyed by `(platform, slug, report_url)`).

**Tradeoff considered:**

| Axis | Per-program (chosen) | Shared DB (alternative) |
|---|---|---|
| Fit with `db.open_db()` + `CURRENT_SCHEMA_VERSION` | Native | Needs a new entry-point |
| Per-program scoring queries (the common Phase B shape) | Trivial | Trivial |
| Cross-program aggregate ("worst FN class across portfolio") | One query per program, union | Single SQL query |
| Cross-program schema-drift risk | Low (migrations run on `open_db`) | Zero (single DB, single schema) |
| Locality with operational state (signals / findings) | Yes | No |

**Reasoning:** Phase B's dominant query shape is per-program (the deliverable is a per-program scoring report at `benchmarks/scores/<platform>-<slug>.md`). The cross-program aggregate is a secondary read — one extra query per program is acceptable cost for the locality and `open_db()` fit. Promote to shared DB only if Phase C's analysis surface starts living in aggregate queries.

## Schema: `benchmark_disclosures`

Two column groups: the disclosure row itself (one per disclosed report), and the provenance of the corpus it came from (replicated per row — denormalised for Phase A; promote to a `benchmark_corpora` join table only if storage cost or update churn justify it).

**Disclosure row:**
- `report_url` — PK
- `title`, `severity`, `disclosed_date`, `bounty_usd`, `asset_pattern`, `vuln_class`, `vector_summary`, `auto_detectable_hint` — directly from the JSON
- `ingested_at` — when this row was last upserted

**Provenance** (added in v5 migration, after coordinator's review surfaced the auditability gap):
- `corpus_source` — `source` field from the JSON
- `corpus_generated_at` — `generated_at` from the JSON
- `in_window_range` — `in_window_range` from the JSON
- `date_precision_note` — `disclosed_date_precision_note` from the JSON (optional; per-corpus)

**Verdict** (NULL until Phase B / operator scores):
- `verdict` — `TP` / `FN` / `inconclusive` / NULL
- `verdict_reason` — free text
- `verdict_set_at` — when verdict was last written
- `scoring_rubric_version` — reserved for Phase B's eventual rubric versioning (allow NULL until a rubric exists)

## Ingest invariant

Ingest is idempotent and never touches verdict columns. Phase B / operator owns those; corpus refresh owns everything else.

## Phase B preview (not in scope yet)

A plugin → `vuln_class` coverage map + a scoring engine that walks rows + the map + each program's scope to emit verdicts. Output: SQLite verdict columns + a markdown report at `benchmarks/scores/<platform>-<slug>.md`. The `scoring_rubric_version` column captures the map version under which each verdict was set, so a map evolution doesn't silently invalidate old verdicts.
