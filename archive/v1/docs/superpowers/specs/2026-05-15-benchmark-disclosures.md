# Disclosure-replay benchmark — design notes

> Operational record for the benchmark feature. Captures the storage-scope decision, the column-set rationale, and the Phase B scoring rubric so the implementation inherits the right assumptions.

## Storage scope decision: per-program SQLite

Per-program `db.sqlite` holds the `benchmark_disclosures` table, alongside `signals` / `findings` / `recon_runs`. Decision recorded after coordinator's cursor-agent review surfaced the alternative (a shared benchmark DB).

**Reasoning:** Phase B's dominant query shape is per-program (one markdown report per program). Cross-program aggregate ("worst FN class across portfolio") is a secondary read — one extra query per program is acceptable cost for the locality and `open_db()` fit. Promote to shared DB only if Phase C's analysis lives in aggregate queries.

## Schema evolution

**v4** (shipped): `benchmark_disclosures` baseline — report fields + verdict columns (NULL until scored).

**v5** (shipped): provenance columns — `corpus_source`, `corpus_generated_at`, `in_window_range`, `date_precision_note`, `scoring_rubric_version` (reserved).

**v6** (planned with Phase B): adds eligibility + verdict provenance:
- `in_window_eligible INTEGER NOT NULL DEFAULT 1` — populated by Phase A ingest from per-row `in_window` field (default True when absent).
- `verdict_source TEXT` — `'scorer'` for verdicts written by the scoring engine; `'operator'` for manual overrides. NULL when verdict NULL.

### Backfill procedure for v6

Migrations are schema-only by design — they take a `sqlite3.Connection`, not a `Paths`. Having the v6 migration read the corpus JSON would break that pattern and tangle migration tests with corpus fixtures. Instead:

1. v6 migration adds `in_window_eligible` with `DEFAULT 1` (correct for new ingests; stale for pre-v6 rows on the 3 already-onboarded programs).
2. **Ingest CLI is updated in the same v6 commit** to populate `in_window_eligible` from per-row JSON `in_window` (absent → 1, `false` → 0).
3. **Deployment procedure**: after deploying v6, run `bin/benchmark-ingest --platform hackerone --program <slug>` once per existing program. Upserts on `report_url` write the correct `in_window_eligible` over the migration default. Documented in the commit message; a `scripts/benchmark-v6-backfill.sh` helper does the loop if it grows.

This trades the "self-contained migration" property for "migrations stay filesystem-pure." The order-of-operations risk (migrate → score → re-ingest) can produce *corrupt* state without the guard below: step 2 writes scorer verdicts to rows that step 3 will then mark ineligible, leaving the invariant "verdict stays NULL when `in_window_eligible = 0`" retroactively violated.

**Self-healing guard (ingest-owned).** Whenever ingest flips a row to `in_window_eligible = 0`, it also clears scorer-owned verdict state on that row in the same statement:

```sql
UPDATE benchmark_disclosures
SET    verdict = NULL,
       verdict_reason = NULL,
       verdict_set_at = NULL,
       scoring_rubric_version = NULL,
       verdict_source = NULL
WHERE  report_url = ?
  AND  in_window_eligible = 0
  AND  verdict_source = 'scorer'
```

The `verdict_source = 'scorer'` guard preserves operator overrides — those are intentional human verdicts that survive an eligibility-flip and continue to inform the markdown report. The scorer-clearing case heals the only retroactive-corruption path: a stale scorer verdict whose row should never have been scored.

The alternative considered (guard i — scorer refuses to run until a "backfill complete" sentinel is set) was *not* rejected on architectural grounds: a per-program sentinel that ingest sets after a successful v6-aware pass is implementable without reading the corpus from the migration layer. The reason guard (ii) wins is **operational**: it converges to the correct state on any ingest run, with no operator action required and no "you forgot to run ingest" failure mode. Guard (i) requires explicit operator awareness ("I must run ingest after migration before scoring") and an extra sentinel column. For Phase B's scale (~21 rows across 3 programs) the self-healing path dominates by simplicity. Promote to guard (i) only if operator workflow turns out to make stale verdicts costly to observe-and-fix.

### `scoring_rubric_version` type note

The v5 reservation declared the column `TEXT`. SQLite's loose typing tolerates any value, but text comparison is lexicographic — `'10' < '2'` is true under naive `< ?` ordering. Two facts:

1. **Stored values are TEXT.** SQLite's TEXT-affinity column declaration converts INTEGER parameter bindings to text at insert time; `typeof(scoring_rubric_version)` will return `'text'` regardless of how Python binds it. Earlier spec drafts claimed Python's `sqlite3` preserved affinity through TEXT columns; verification (`CREATE TABLE t(v TEXT); INSERT ... (10,); SELECT typeof(v)` returns `'text'`) shows that's wrong. Drop that assumption.
2. **Reads always cast** before comparison: `CAST(scoring_rubric_version AS INTEGER) < ?`. The atomic-conditional-write WHERE clause in this spec uses CAST. This handles both string-stored and integer-stored values correctly.

No type-rewrite migration required for correctness. A future schema rewrite may promote the column to declared INTEGER affinity, but the CAST contract makes it optional. Tests cover the lexicographic edge case (e.g. version `'2'` must not overwrite version `'10'` under the WHERE clause).

## Phase B scoring rubric

The scorer is two inputs in, three outputs out: `(disclosure_row, coverage_map) → (verdict, verdict_reason, scoring_rubric_version)`.

**Truth table** keyed on `(vuln_class, auto_detectable_hint)`:

| vuln_class coverage in map | auto_detectable_hint | verdict |
|---|---|---|
| no plugins (zero entries) | any | **FN** — reason: "no plugin covers `<vuln_class>`" |
| ≥1 plugin | `regex-friendly` | **inconclusive** — reason: "plugin(s) cover; regex-pattern fit suggests likely TP but operator review needed" |
| ≥1 plugin | `requires-auth` | **FN** — reason: "plugin covers class but no authenticated scanning primitives" |
| ≥1 plugin | `requires-business-logic` | **FN** — reason: "class-level coverage doesn't cover flow-context variants" |
| ≥1 plugin | `requires-payload-crafting` | **FN** — reason: "plugin covers class but specific payload not in template set" |
| ≥1 plugin | `requires-chain` / `requires-fuzzing` / `unclear` | **inconclusive** — reason: "manual review needed" |

**No v1 entry should be TP-default.** TPs are operator-assertable post-hoc per the override pattern below.

**Eligibility short-circuit (scorer):** if `in_window_eligible = 0`, the scorer **never writes verdict fields for the row**. The scorer cannot create a non-NULL verdict on an ineligible row.

**Operator-override precedence:** an operator-written verdict (verdict_source = 'operator') survives an eligibility flip — the self-healing ingest only clears scorer rows. Counting and display rules respect operator authority:

- A row with `verdict_source = 'operator'` is shown in the detail table with its verdict regardless of eligibility, and counted in the summary table under its verdict bucket (`TP` / `FN` / `inconclusive`). The eligibility column is shown alongside for transparency, but does not override the verdict.
- A row with `verdict_source = 'scorer' AND verdict IS NOT NULL AND in_window_eligible = 1` is shown in the detail table with its verdict and counted in the summary table under its verdict bucket — the normal scored path.
- A row with `verdict IS NULL AND in_window_eligible = 0` counts as `excluded` and is the only source of the `excluded` summary column. Operator-overridden ineligible rows are NOT in this count.
- A row with `verdict IS NULL AND in_window_eligible = 1` is `unscored` (a transient state — next score pass fills it).

Single source of truth for "excluded" is `verdict IS NULL AND in_window_eligible = 0`. Verdict remains tri-valued with NULL meaning "unscored or scorer-skipped-due-to-ineligibility".

## Coverage map: `benchmarks/coverage_map.yaml`

Single repo-level YAML, top-level `coverage_map_version: 1` integer. Loaded at scoring time; the version written into `scoring_rubric_version` for each updated row.

```yaml
coverage_map_version: 1
coverage:
  - vuln_class: Info-Disclosure
    plugins: [nuclei, sourcemap-scan, graphql-probe]
    notes: variant-dependent; unauthenticated only.
  - vuln_class: IDOR
    plugins: []
    notes: no current plugin targets IDOR specifically.
  - vuln_class: Auth-Bypass
    plugins: []
    notes: no current plugin.
  - vuln_class: SSRF
    plugins: []
    notes: no current SSRF detector wired in.
  - vuln_class: Logic-Flaw
    plugins: []
    notes: scanner-out-of-class — definitionally not regex/template catchable.
  - vuln_class: Misc
    plugins: []
    notes: class-too-broad to claim coverage.
```

`katana-crawl` is intentionally absent — it produces context (discovered URLs), not detections, and shouldn't claim plugin status.

## Atomic conditional write

Verdict writes are a single transaction with a precondition baked into the WHERE clause:

```sql
UPDATE benchmark_disclosures
SET    verdict = ?, verdict_reason = ?, verdict_set_at = ?,
       verdict_source = 'scorer', scoring_rubric_version = ?
WHERE  report_url = ?
  AND  in_window_eligible = 1
  AND  (verdict IS NULL
        OR (verdict_source = 'scorer'
            AND CAST(scoring_rubric_version AS INTEGER) < ?))
```

No read-then-write. The scorer can only overwrite older-rubric scorer rows; an `operator` row stays put across re-scores. `--force` flag is reserved (not built) for the rubric-evolution case where the operator wants to wipe their own prior overrides too.

## Scoring function signature

```python
def score_program(paths, *, platform: str, slug: str) -> ScoringSummary
```

Loads `benchmarks/coverage_map.yaml`, reads its `coverage_map_version`, walks `benchmark_disclosures` rows for the program, emits per-row verdicts, writes back. No `coverage_map_version` argument — the YAML is the source of truth. CLI accepts an optional `--assert-coverage-map-version=N` for CI/operator sanity-checking.

## Markdown report

Per-program at `benchmarks/scores/<platform>-<slug>.md`. Two tables:

**Summary table** (Phase 6 plugin-gap roadmap):

| vuln_class | TP | FN | inconclusive | excluded | plugins |
|---|---|---|---|---|---|
| IDOR | 0 | 4 | 0 | 0 | (none) |
| Info-Disclosure | 0 | 0 | 8 | 0 | nuclei / sourcemap-scan / graphql-probe |
| … |

**Detail table** (operator workload, FN first):

| verdict | vuln_class | severity | report_url | reason |
|---|---|---|---|---|
| FN | IDOR | high | https://… | no plugin covers IDOR |
| … |

Header lines: program slug, generated_at, `coverage_map_version` applied, totals.

## Operator override pattern

Until `bin/benchmark-verdict` ships in Phase C, operators set verdicts via direct SQL on the program DB:

```sql
UPDATE benchmark_disclosures
SET    verdict = 'TP',
       verdict_reason = 'manually replayed against asset, plugin fires',
       verdict_source = 'operator',
       verdict_set_at = '2026-05-15T12:00:00Z',
       scoring_rubric_version = 1
WHERE  report_url = 'https://hackerone.com/reports/2209750';
```

The atomic-conditional-write invariant above guarantees re-running the scorer never clobbers an `operator` row regardless of rubric evolution.

## Phase split summary

- **Phase A (shipped)**: corpus + ingest + provenance columns (v4 + v5).
- **Phase B (this design)**: v6 migration, coverage map YAML, scoring engine, markdown report.
- **Phase C (deferred)**: `bin/benchmark-verdict` operator CLI, shared-DB promotion if aggregate queries dominate, rubric-version evolution tooling.
