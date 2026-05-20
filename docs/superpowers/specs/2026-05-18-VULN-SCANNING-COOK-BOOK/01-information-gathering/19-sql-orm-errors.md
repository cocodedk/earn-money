---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 19
slug: sql-orm-errors
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.19 SQL/ORM errors

> Phase 1 — Information gathering · Category: Error disclosure

<!--
GPT-5.5: Enrichment zone — paste-ready spec contract for LLM-assisted implementation.

Goal: enrich this spec so a coding agent can implement it safely and consistently.

PROTECTED — do not modify:
- YAML frontmatter (between `---` fences at top of file).
- Title heading, blockquote breadcrumb, and the `##` section headings.

EDITABLE — fill these:
- The body under each `##` section. Sub-headings (`###`), lists, code blocks, tables welcome.

OUTPUT FORMAT:
- Return raw markdown directly. Do NOT wrap the response in a ` ```markdown ` code fence.
- Inside the body, use exactly 3 backticks for code fences. No 4-backtick blocks.

CONTENT RULES:
- Use shared `ScanTarget` and `Evidence` from ../00-shared-schema.md. Do not redefine them.
- Define only stub-specific `<Name>Signature` and `<Name>Finding` types.
- Detection is deterministic. AI is `None` unless a deterministic gap is named under Safety.
- Pass/fail check has explicit assertions, including negative ones (what must NOT happen).
- Confidence: `low | medium | high`. Finding status: `candidate | confirmed | rejected | stale`.
- Never hard-code hostname → expected tech; detect from response evidence.
- Follow the Coding-agent rules in ../00-shared-schema.md.
-->

## Purpose

Detect SQL database and ORM error messages exposed through HTTP responses. A runner cares because these errors can leak table names, column names, SQL fragments, driver names, framework internals, filesystem paths, and query structure. This finding does not prove SQL injection by itself; it records evidence that backend data-access errors are visible to unauthenticated or low-privilege clients.

## Inputs

The runner receives a shared `ScanTarget` and uses the normal HTTP client, evidence store, scope rules, redirect policy, and timeout budget from the shared scanner.

Required input:

* `ScanTarget` from `../00-shared-schema.md`.

Optional config:

| Name                        | Type    | Default                                         | Notes                                                                                                                                   |
| --------------------------- | ------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `max_candidate_urls`        | integer | `40`                                            | Maximum URLs to test after crawler/imported routes are normalized.                                                                      |
| `max_requests_per_url`      | integer | `3`                                             | Hard cap for deterministic variants per URL.                                                                                            |
| `request_timeout_ms`        | integer | shared default                                  | Per-request timeout.                                                                                                                    |
| `follow_redirects`          | boolean | shared default                                  | Must match shared HTTP policy.                                                                                                          |
| `include_query_param_probe` | boolean | `true`                                          | Sends one safe malformed query-parameter request when a URL already has query parameters or known parameter names.                      |
| `include_path_probe`        | boolean | `false`                                         | Disabled by default. May append one harmless path suffix only when the route is already in scope and known to tolerate path parameters. |
| `max_body_bytes_to_scan`    | integer | `262144`                                        | Scanner inspects at most this many bytes from each response body. Store truncation metadata in `Evidence`.                              |
| `interesting_statuses`      | array   | `[400, 404, 405, 409, 422, 500, 501, 502, 503]` | Error disclosure can appear in non-500 responses too.                                                                                   |
| `baseline_compare`          | boolean | `true`                                          | Compare normal and probed responses when possible.                                                                                      |

Candidate URL sources:

* URLs discovered by earlier crawl phases.
* URLs from sitemap, robots, JavaScript route extraction, OpenAPI/Swagger discovery, and manually supplied target paths.
* URLs that already contain query parameters.
* API endpoints returning JSON, XML, HTML, text, or framework error pages.

Do not invent endpoints. Do not scan outside the shared target scope.

## Detection logic

Detection is deterministic and evidence-based.

### Request plan

For each candidate URL:

1. Send a baseline `GET` request unless an identical response is already stored from an earlier phase.
2. Inspect status, headers, content type, and body for SQL/ORM error signatures.
3. If `include_query_param_probe=true`, send at most one safe malformed query-parameter request:

   * For URLs that already contain parameters, replace one parameter value with a benign malformed sentinel.
   * For URLs with known parameter names from crawl/import data, add one query parameter using a known name.
   * Do not add many parameters.
   * Do not fuzz.
4. Optionally inspect `POST` or other methods only when a previous crawler/API discovery phase has already captured a safe, read-only request shape. Do not invent mutating requests.
5. Store each inspected response as `Evidence`.

Safe sentinel values must be inert strings, not SQL injection payloads. Examples:

```text
scanner_sql_orm_error_probe_%27
scanner_sql_orm_error_probe_%22
scanner_sql_orm_error_probe_%5C
```

The sentinel may include URL-encoded quote or backslash characters because the purpose is to trigger parser/type errors, not to alter SQL logic. Do not use boolean logic, comments, delays, stacked statements, UNION clauses, file reads, database functions, or DBMS-specific exploit syntax.

### Signature sources

Scan these response fields:

* HTTP status code.
* `Content-Type`.
* Selected safe headers that may contain framework or error metadata.
* Response body, capped by `max_body_bytes_to_scan`.
* JSON error fields such as `error`, `message`, `detail`, `exception`, `stack`, `trace`, `errors`.
* HTML title, preformatted blocks, stack trace blocks, and visible text.

Do not scan or persist cookies, authorization headers, session tokens, or credentials except through the shared redaction rules.

### SQL error signatures

Match case-insensitively against common database error text. A match is stronger when the response also contains SQL fragments, driver names, stack traces, ORM names, or a server error status.

Examples of high-signal SQL/database indicators:

```text
SQL syntax
syntax error at or near
unterminated quoted string
unclosed quotation mark
quoted string not properly terminated
You have an error in your SQL syntax
Warning: mysql_
mysqli_sql_exception
PDOException
SQLSTATE[
ORA-
Oracle error
PostgreSQL
pg_query
psycopg
SQLiteException
sqlite3.OperationalError
Microsoft OLE DB Provider for SQL Server
SQL Server Native Client
System.Data.SqlClient
Npgsql
MySqlException
MariaDB
SequelizeDatabaseError
PrismaClientKnownRequestError
QueryFailedError
ActiveRecord::StatementInvalid
Doctrine\DBAL
HibernateException
JDBCException
org.hibernate.exception
```

Examples of supporting SQL-fragment indicators:

```text
SELECT
INSERT
UPDATE
DELETE
FROM
WHERE
ORDER BY
GROUP BY
LIMIT
OFFSET
JOIN
near '?'
at line 1
column does not exist
relation does not exist
table does not exist
unknown column
invalid column name
ambiguous column
duplicate key value
foreign key constraint
```

Supporting SQL-fragment indicators alone are not enough for a confirmed finding. They can raise a candidate only when combined with error context.

### ORM and framework signatures

Detect ORM-level error disclosures when they reveal backend data-access internals. Examples:

```text
SequelizeDatabaseError
SequelizeValidationError
PrismaClientKnownRequestError
PrismaClientValidationError
TypeORMError
QueryFailedError
ActiveRecord::StatementInvalid
ActiveRecord::RecordNotFound
Doctrine\DBAL\Exception
Illuminate\Database\QueryException
Eloquent
HibernateException
JDBCException
Entity Framework
DbUpdateException
MongoServerError
MongooseError
Neo.ClientError.Statement.SyntaxError
```

ORM validation errors that only say a user field is invalid are not enough. The finding needs evidence of backend query, database driver, model/table/column names, stack traces, or internal exception class names.

### Classification

Create a finding when one or more signatures match after redaction.

Confidence rules:

| Confidence | Required evidence                                                                                                                                        |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `high`     | Response contains a known SQL/ORM exception or DBMS error class plus SQL/database context, stack trace, driver name, table/column name, or SQL fragment. |
| `medium`   | Response contains a known SQL/ORM exception or DBMS error class, but little extra context.                                                               |
| `low`      | Response contains weak SQL-like error text without DBMS, ORM, driver, stack trace, or query context.                                                     |

Status rules:

| Status      | Meaning                                                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `candidate` | One or more signatures matched but baseline/probe comparison is incomplete, weak, or ambiguous.                                            |
| `confirmed` | High-signal error disclosure is visible in an in-scope HTTP response.                                                                      |
| `rejected`  | A candidate was tested and found to be a generic user-facing validation error, static documentation, honeypot marker, or scanner artifact. |
| `stale`     | Previously stored evidence no longer reproduces and current response no longer contains the signature.                                     |

Severity guidance:

* Default severity is `info` for generic ORM class disclosure.
* Use `low` when database type, driver, SQL fragment, table name, column name, filesystem path, or stack frame is exposed.
* Use `medium` only when the error discloses sensitive schema details or query fragments that materially help exploitation.
* Do not report `high` or `critical` from this check alone. This check detects disclosure, not exploitation.

### False-positive controls

Reject or downgrade when:

* The text appears in a blog post, documentation page, changelog, tutorial, source code viewer, or static sample.
* The page is intentionally showing examples of SQL errors.
* The response is from a known public documentation host outside the scan target.
* The only match is a generic phrase like `database error` with no concrete backend detail.
* The only evidence is a frontend error message with no server-side context.
* The response body is a scanner-generated test page or fixture marker.
* The signature appears only inside quoted user input that the scanner sent.

Never hard-code target hostnames, app names, or fixtures to expected technologies. Detect from response evidence only.

## Persistence

Use the shared `ScanTarget` and `Evidence` types from `../00-shared-schema.md`. Do not redefine them here.

Define only these stub-specific types:

```ts
export type SqlOrmErrorConfidence = "low" | "medium" | "high";
export type SqlOrmErrorFindingStatus = "candidate" | "confirmed" | "rejected" | "stale";

export interface SqlOrmErrorSignature {
  id: string;
  family:
    | "mysql"
    | "postgresql"
    | "sqlite"
    | "mssql"
    | "oracle"
    | "mariadb"
    | "orm"
    | "driver"
    | "generic_sql"
    | "other";
  name: string;
  pattern: string;
  pattern_type: "literal" | "regex";
  case_sensitive: boolean;
  confidence_hint: SqlOrmErrorConfidence;
  requires_context: boolean;
  description: string;
}

export interface SqlOrmErrorFinding {
  id: string;
  target_id: string;
  status: SqlOrmErrorFindingStatus;
  confidence: SqlOrmErrorConfidence;
  severity: "info" | "low" | "medium";
  url: string;
  method: "GET" | "POST" | "HEAD" | "OPTIONS" | "OTHER";
  status_code: number | null;
  content_type: string | null;
  matched_signatures: SqlOrmErrorSignature[];
  evidence_ids: string[];
  baseline_evidence_id?: string;
  probe_evidence_id?: string;
  disclosed_families: SqlOrmErrorSignature["family"][];
  disclosed_terms: string[];
  disclosed_schema_terms: string[];
  disclosed_driver_terms: string[];
  disclosed_stack_terms: string[];
  snippet_redacted: string;
  response_was_truncated: boolean;
  probe_used: boolean;
  probe_parameter?: string;
  false_positive_reason?: string;
  first_seen_at: string;
  last_seen_at: string;
}
```

Persistence rules:

* Store full raw responses only through the shared `Evidence` mechanism.
* Store `snippet_redacted` as a short, redacted excerpt around the match.
* Store offsets or line numbers when the shared `Evidence` model supports them.
* Do not store secrets, cookies, authorization headers, or full request bodies in this finding.
* `matched_signatures` must reference deterministic signature IDs.
* `evidence_ids` must include every response used to justify the finding.
* `baseline_evidence_id` and `probe_evidence_id` should be set when both exist.
* `disclosed_terms` must be redacted and deduplicated.
* `disclosed_schema_terms` should include safe table/column/model names only when they are visible in evidence.
* If a finding is later not reproducible, keep the old evidence and mark the current finding `stale`.

## Safety

This check is read-only by default.

Allowed behavior:

* `GET`, `HEAD`, and `OPTIONS` requests.
* One baseline request per candidate URL.
* One safe malformed query-parameter request per candidate URL when enabled.
* Inspection of previously captured safe API responses.
* Redacted storage of short error snippets.

Restricted behavior:

* Do not use exploit SQL payloads.
* Do not use boolean-based, time-based, UNION-based, stacked-query, comment-based, or DBMS-function payloads.
* Do not attempt authentication bypass.
* Do not infer exploitability from error disclosure alone.
* Do not submit forms unless a prior phase has marked the form as read-only and safe.
* Do not send mutating methods such as `PUT`, `PATCH`, or `DELETE`.
* Do not send `POST` unless the request shape was already captured and marked safe by shared scanner policy.
* Do not brute force parameter names.
* Do not fuzz with wordlists.
* Do not increase concurrency beyond shared scanner limits.
* Do not scan out-of-scope URLs from error messages.
* Do not follow database connection strings or file paths found in responses.
* Do not include cookies, tokens, or credentials in snippets.

Payload restrictions:

* Probe values must be inert malformed strings.
* Payloads must not contain SQL operators such as `OR`, `AND`, `UNION`, `SLEEP`, `BENCHMARK`, `WAITFOR`, `LOAD_FILE`, `xp_`, `--`, `/*`, `#`, or stacked statement separators.
* Payloads must not attempt to change query results.
* Payloads must not attempt to delay the server.

PII handling:

* Redact email addresses, phone numbers, tokens, session IDs, API keys, database passwords, connection strings, and long unique identifiers from finding snippets.
* Use shared redaction utilities before persistence.
* Keep raw body access limited to the shared evidence store.

AI involvement: `None`.

Deterministic gap:

* No AI is needed. Pattern matching, context checks, baseline comparison, redaction, and classification are deterministic.
* If a future implementation adds AI-assisted explanation, it must consume only already-confirmed findings and redacted evidence snippets. It must not decide status, severity, confidence, or scope.

## Pass/fail check

The implementation passes when all assertions below are true.

Positive assertions:

* Given a response body containing `SQLSTATE[42000]` and `You have an error in your SQL syntax`, the scanner creates a `SqlOrmErrorFinding`.
* Given a response body containing `SequelizeDatabaseError` with a SQL fragment, the finding confidence is `high`.
* Given a response body containing `PrismaClientKnownRequestError` with a model or field name, the finding confidence is at least `medium`.
* Given a PostgreSQL error such as `syntax error at or near`, the signature family is `postgresql`.
* Given a Microsoft SQL Server error such as `System.Data.SqlClient.SqlException`, the signature family is `mssql`.
* Given an Oracle error such as `ORA-00933`, the signature family is `oracle`.
* Given an SQLite error such as `sqlite3.OperationalError`, the signature family is `sqlite`.
* Given a weak `database error` string without backend context, the scanner may create only a `candidate` with `low` confidence.
* A confirmed finding includes at least one `Evidence` ID.
* A confirmed finding includes a redacted snippet around the matched text.
* A finding created from a probe records `probe_used=true`.
* A finding created from baseline-only evidence records `probe_used=false`.
* If both baseline and probe responses exist, their evidence IDs are stored separately.
* If a previously confirmed finding no longer reproduces, the new status is `stale`, not silently deleted.
* Redaction runs before `snippet_redacted` is persisted.

Negative assertions:

* The scanner must not report a confirmed finding from a documentation page that merely contains SQL error examples.
* The scanner must not report a confirmed finding from text that appears only inside the scanner-supplied probe value.
* The scanner must not infer SQL injection exploitability.
* The scanner must not mark severity as `high` or `critical` from this check alone.
* The scanner must not send `UNION SELECT`, `OR 1=1`, `SLEEP`, stacked statements, comments, or DBMS-specific exploit payloads.
* The scanner must not use mutating HTTP methods.
* The scanner must not brute force parameter names.
* The scanner must not follow URLs, file paths, or hostnames disclosed inside an error message unless already in shared scan scope.
* The scanner must not store cookies, authorization headers, API keys, session IDs, or database passwords in the finding snippet.
* The scanner must not hard-code hostname-to-technology expectations.
* The scanner must not call an LLM.
* The scanner must not retry indefinitely after timeouts or TLS errors.
* The scanner must not create duplicate findings for the same URL, method, signature family, and evidence hash.

Example deterministic test cases:

```ts
expect(mysqlFinding.status).toBe("confirmed");
expect(mysqlFinding.confidence).toBe("high");
expect(mysqlFinding.disclosed_families).toContain("mysql");
expect(mysqlFinding.evidence_ids.length).toBeGreaterThan(0);

expect(documentationExample.status).not.toBe("confirmed");
expect(documentationExample.false_positive_reason).toBeDefined();

expect(sentPayloads).not.toContain("UNION SELECT");
expect(sentPayloads).not.toContain("OR 1=1");
expect(sentPayloads).not.toContain("SLEEP");
expect(llmCalls.length).toBe(0);
```

## Test fixtures

Use one or more controlled fixtures. The runner should not depend on a live internet target.

Recommended fixture: `webgoat`

* Use a lesson or test route that can return database/ORM-style errors in a controlled container.
* Prefer a route where malformed input returns an error page without modifying server state.
* If WebGoat does not expose a stable SQL/ORM error for this exact check, create a small local fixture instead.

Secondary fixture: `dvwa`

* DVWA can expose database errors in deliberately vulnerable SQL injection pages when configured for low security.
* Use only safe malformed values that cause visible errors.
* Do not use exploit payloads.
* Run only inside the local fixture container.

Fallback fixture: `sql-orm-error-fixture`

Create a minimal local HTTP service with deterministic routes:

| Route               | Response                                                             | Expected result             |
| ------------------- | -------------------------------------------------------------------- | --------------------------- |
| `/mysql-error`      | 500 HTML with `SQLSTATE[42000]` and MySQL syntax text                | confirmed, high, mysql      |
| `/postgres-error`   | 500 JSON with `syntax error at or near` and `Npgsql`                 | confirmed, high, postgresql |
| `/sqlite-error`     | 500 text with `sqlite3.OperationalError`                             | confirmed, high, sqlite     |
| `/mssql-error`      | 500 HTML with `System.Data.SqlClient.SqlException`                   | confirmed, high, mssql      |
| `/oracle-error`     | 500 text with `ORA-00933`                                            | confirmed, high, oracle     |
| `/sequelize-error`  | 500 JSON with `SequelizeDatabaseError` and a redacted query fragment | confirmed, high, orm        |
| `/generic-db-error` | 500 text with only `database error`                                  | candidate, low              |
| `/docs/sql-errors`  | 200 documentation text showing SQL error examples                    | rejected                    |
| `/echo?x=`          | 200 response echoing input probe only                                | rejected                    |
| `/normal`           | 200 normal page                                                      | no finding                  |

Fixture requirements:

* Runs in Docker with the existing test harness.
* Has deterministic response bodies.
* Does not require external network access.
* Does not require credentials unless the shared fixture system already supports them.
* Provides stable content types and status codes.
* Includes at least one JSON response and one HTML response.
* Includes one redaction case with a fake connection string or password to verify snippet redaction.

## Acceptance criteria

The implementation is acceptable when:

* It uses shared `ScanTarget` and `Evidence` without redefining them.
* It defines only `SqlOrmErrorSignature` and `SqlOrmErrorFinding` as stub-specific types.
* It is deterministic and does not call an LLM.
* It obeys shared scope, timeout, redirect, TLS, evidence, logging, and redaction rules.
* It performs only read-only or explicitly safe requests.
* It sends no exploit SQL payloads.
* It caps requests per URL and total candidate URLs.
* It handles HTML, JSON, XML, and plain-text responses.
* It handles compressed responses through the shared HTTP client.
* It handles invalid encodings without crashing.
* It handles TLS errors gracefully according to shared scanner policy.
* It stores redacted snippets and evidence IDs.
* It deduplicates findings by target, URL, method, signature family, and evidence hash.
* It marks old findings `stale` when evidence no longer reproduces.
* It avoids false positives from documentation, tutorials, sample code, echoed input, and generic frontend messages.
* It completes within the configured scan budget.
* It has unit tests for signature matching, confidence classification, redaction, false-positive rejection, stale handling, and payload restrictions.
* It has fixture/integration tests for at least MySQL, PostgreSQL, SQLite, one ORM error, one documentation false positive, and one echoed-input false positive.
* It logs enough operational metadata for debugging without logging secrets or full sensitive payloads.
* It does not hard-code fixture hostnames or expected technologies.
* Re-running the scanner against the same fixture is idempotent and does not create duplicate active findings.

