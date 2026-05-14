# GraphQL Introspection Probe Plan

> **For agentic workers:** Use superpowers:executing-plans. Checkbox steps.

**Goal:** For each in-scope HTTP service, try common GraphQL endpoint paths and check whether introspection (\`__schema\`) is enabled. Introspection-enabled production GraphQL is a real finding because the leaked schema accelerates every subsequent attack against the same API.

**Architecture:** Pure-function tool (\`graphql_tool.py\`) + runner (\`graphql_probe.py\`) + CLI. Tool layer is one POST per URL. Sequential per target so RoE rate cap holds naturally (~3-5 req/s in practice).

## Anti-goals

- No schema dump beyond detection. Emit a Signal saying "introspection enabled" — the operator pulls the full schema by hand if they want to file. (Bandwidth+disk hygiene.)
- No batch / authenticated probing. Public endpoint only. v2 may add auth headers via roe.md.
- No mutation queries. Introspection is read-only by design.

## File structure

| Path | ~Lines | Purpose |
|------|--------|---------|
| \`src/earn_money/recon/graphql_tool.py\` (new) | 130 | \`build_query()\`, \`COMMON_PATHS\`, \`probe(client, base_url, …) → Signal | None\` |
| \`src/earn_money/runners/graphql_probe.py\` (new) | 170 | Gate → load services → iterate paths → scope-filter signals → record |
| \`src/earn_money/runners/graphql_probe_cli.py\` (new) | 130 | httpx.Client + sequential loop + exit ladder |
| \`bin/graphql-probe\` (new) | 17 | Shell wrapper |
| \`tests/recon/test_graphql_tool.py\` | 100 | Query builder + response parser with httpx.MockTransport |
| \`tests/runners/test_graphql_probe.py\` | 130 | Gate refusal, scope filter, signal insertion, RoE manifest |

## Signal shape

\`tool="graphql-probe"\`, \`signal_type="introspection_enabled"\`, severity \`medium\`. Signature: \`graphql|<endpoint_path>|introspection\`. Payload includes the response's first 200 chars of \`__schema.queryType.name\` and a sample type name list (max 10) so the operator sees the introspection actually returned schema material.

## Common paths to probe

\`/graphql\`, \`/api/graphql\`, \`/v1/graphql\`, \`/v2/graphql\`, \`/query\`, \`/api/v1/graphql\`. Six paths per target. Each is a single POST; out-of-scope hosts are dropped before any request.

## Scope safety

Same shape as sourcemap-scan: \`in_scope_host\` callback re-checked against live scope before every fetch. Targets come from \`http_services\` already filtered, but the live re-check stops a scope-narrowed asset from sending traffic.

## Tasks

1. Tool wrapper + tests (TDD)
2. Runner + tests (mock tool_run)
3. CLI + bin wrapper
4. /simplify + /code-review
5. PR + merge + sync
