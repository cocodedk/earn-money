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

## Workflow

Each leaf bullet flows through four stages: **spec → plan → implement → persist**.

1. **Spec.** GPT-5.5 enriches the spec stub's body sections — Intent, Detection technique, Fixture, Pass/fail check, Persistence, AI involvement. The operator reviews; flips spec frontmatter `status:` to `in-progress` when picking it up, `done` once approved. Assigns `fixture:` to `juice-shop`/`dvwa`/`webgoat`/`<name>` when known.
2. **Plan.** Every spec has a matching plan stub at the mirror path under [`docs/superpowers/plans/2026-05-18-VULN-SCANNING-COOKBOOK/`](../../plans/2026-05-18-VULN-SCANNING-COOKBOOK/). Once the spec is `done`, draft the plan body (Summary, Files to touch, TDD steps, Verification, Persistence wiring) and flip plan frontmatter `status:` to `drafted` → `approved` → `implemented` → `verified` as work progresses.
3. **Implement.** TDD per the plan. Each runner is gated by passing tests against the assigned fixture URL before merging.
4. **Persist.** Every runner writes findings into the cookbook backend. Schema is deferred — the cross-module pattern will be designed after the first 3–5 plans land, once we see what the result shapes have in common. AI involvement is layered on top of the populated result store, not the recon path.

A phase ships only when **every** spec is `done` and **every** plan is `verified` for that phase. No partial coverage advances.

## Progress

[`PROGRESS.md`](PROGRESS.md) is a generated view of every spec and plan's YAML frontmatter. Regenerate after editing a stub:

```bash
.venv/bin/python scripts/cookbook_progress.py
```

The script reads two fields per spec (`status`, `fixture`) and one per plan (`status`), then writes a two-column rollup (`spec / plan`) at the cookbook root. Commit the frontmatter edits and the regenerated `PROGRESS.md` together. Never hand-edit `PROGRESS.md` — the next regen will clobber it.

### Frontmatter — script-managed, do not delete

Both spec and plan stubs open with a YAML frontmatter block fenced by `---`. **Don't remove the fences or the lines inside them.** A comment at the top of each block marks it as managed. The body below the second `---` is yours and GPT-5.5's.

| File | Field | Allowed values |
|------|-------|----------------|
| spec | `status` | `pending` · `in-progress` · `blocked` · `done` |
| spec | `fixture` | `juice-shop` · `dvwa` · `webgoat` · any slug · `tbd` |
| plan | `status` | `pending` · `drafted` · `approved` · `implemented` · `verified` |

`phase`, `spec`, and `slug` are file-identity — never change them. `spec_file`, `implementation_file`, and `test_file` (plan-only) are free-form path references.

## Tooling boundary

**AI is not the automation.** Default to deterministic tooling — nuclei templates, ffuf/feroxbuster, header parsers, regex matchers, schema diffs. Reach for AI only where no deterministic option fits the bullet's intent, and the spec's `## AI involvement` section names that boundary explicitly.

Three vulnerable-app containers are already running on `target.cocode.dk` (see [`../../../CLAUDE.md`](../../../CLAUDE.md) `## Test fixtures`): OWASP Juice Shop, DVWA, WebGoat. Pick whichever exposes the technique most cleanly. If none cover a bullet, install a new fixture container on `target.cocode.dk` first and document its slug in the spec's `fixture:` field.

## Provenance

Initial playbook drafted by GPT-5.5-extended. Source file preserved as
`2026-05-18-VULN-SCANNING-COOK-BOOK-PRODUCT-SPECIFICATIONS.md` in this folder.
The 24 numbered folders above are the canonical per-section breakdown — edit
the per-bullet specs inside, not the source.
