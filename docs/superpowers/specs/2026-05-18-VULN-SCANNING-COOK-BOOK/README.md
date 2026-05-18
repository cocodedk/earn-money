# Vuln-Scanning Cook-Book

Coverage map for authorized webapp pentests. Each section enumerates a class of
attack vectors. The engine tags every discovered input, endpoint, form, script,
header, cookie, and workflow against one or more of these categories, then
chooses safe tests from what the program's `roe.md` allows.

Base structure follows [OWASP WSTG][wstg]; modern web-specific classes (request
smuggling, cache poisoning, GraphQL, JWT, race conditions, …) draw on the
PortSwigger Web Security Academy.

[wstg]: https://owasp.org/www-project-web-security-testing-guide/

## Sections

1. [Information gathering](01-information-gathering/) — 25 specs
2. [Authentication](02-authentication/) — 22 specs
3. [Session management](03-session-management/) — 16 specs
4. [Access control](04-access-control/) — 15 specs
5. [Input validation and injection](05-input-validation-and-injection/) — 16 specs
6. [Cross-site scripting](06-cross-site-scripting/) — 20 specs
7. [CSRF and browser-side request abuse](07-csrf-and-browser-side-request-abuse/) — 7 specs
8. [File upload and file handling](08-file-upload-and-file-handling/) — 15 specs
9. [Path traversal and file inclusion](09-path-traversal-and-file-inclusion/) — 8 specs
10. [Server-side request forgery](10-server-side-request-forgery/) — 8 specs
11. [API security](11-api-security/) — 17 specs
12. [Business logic](12-business-logic/) — 15 specs
13. [Race conditions](13-race-conditions/) — 7 specs
14. [Deserialization and object parsing](14-deserialization-and-object-parsing/) — 6 specs
15. [Client-side security](15-client-side-security/) — 12 specs
16. [CORS and cross-origin policy](16-cors-and-cross-origin-policy/) — 6 specs
17. [HTTP request/response handling](17-http-request-response-handling/) — 8 specs
18. [Security headers and browser hardening](18-security-headers-and-browser-hardening/) — 8 specs
19. [Cryptography and secrets](19-cryptography-and-secrets/) — 8 specs
20. [Logging, monitoring, and privacy](20-logging-monitoring-and-privacy/) — 7 specs
21. [Infrastructure and deployment exposure](21-infrastructure-and-deployment-exposure/) — 9 specs
22. [Third-party integrations](22-third-party-integrations/) — 7 specs
23. [Denial of service, within RoE](23-denial-of-service-within-roe/) — 7 specs
24. [AI/LLM-specific webapp vectors](24-ai-llm-specific-webapp-vectors/) — 9 specs

**Total:** 278 micro-spec stubs across 24 phases.

## Progress

Live status of every spec is in [`PROGRESS.md`](PROGRESS.md). It's a generated
view of each stub's `**Status:**` and `**Fixture:**` lines — single source of
truth lives in the stubs themselves; the rollup is a checked-in lockfile.

Update flow:

1. Edit the per-spec stub: set `**Status:** pending|in-progress|blocked|done`
   and add a `**Fixture:** juice-shop|dvwa|webgoat|<name>` line when assigned.
2. Run `python3 scripts/cookbook_progress.py` from the repo root.
3. Commit the stub edits and the regenerated `PROGRESS.md` together.

Never hand-edit `PROGRESS.md` — the next regen would clobber it.

## Implementation approach

24 phases, one per top-level section above. Each phase is gated — phase N must
work end-to-end against `target.cocode.dk` before phase N+1 begins. No phase
moves forward on partial coverage.

**AI is not the automation.** Default to deterministic tooling — nuclei
templates, ffuf/feroxbuster, header parsers, regex matchers, schema diffs.
Reach for AI only where no deterministic option fits the bullet's intent, and
the spec names that boundary explicitly.

Per phase:

1. **Fill specs.** Each phase folder ships with stubs (`NN-<slug>/01-…md` …)
   plus an `00-overview.md` carrying the original bullet list. When the phase
   starts, each stub is filled with detection technique, fixture, pass/fail
   check, finding schema, and AI-involvement boundary.
2. **Build.** Implement the runner per the filled spec.
3. **Test.** Three vulnerable-app containers are already running on
   `target.cocode.dk`: OWASP Juice Shop, DVWA, and WebGoat. Pick whichever
   fixture exposes the technique most cleanly. If none of the three covers a
   technique, install a new fixture container on `target.cocode.dk` first,
   then write the test against it.
4. **Gate.** A phase ships only when every bullet has a passing test against
   its chosen fixture.

## Provenance

Initial playbook drafted by GPT-5.5-extended. Source file preserved as
`2026-05-18-VULN-SCANNING-COOK-BOOK-PRODUCT-SPECIFICATIONS.md` in this folder.
The 24 numbered folders above are the canonical per-section breakdown — edit
the per-bullet specs inside, not the source.
