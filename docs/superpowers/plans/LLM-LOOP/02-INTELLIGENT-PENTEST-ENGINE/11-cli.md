# Task 11: Add CLI entry point

## Create

```text
src/earn_money/agent/hacker_loop_cli.py
tests/agent/test_hacker_loop_cli.py
bin/probe-target
```

## Requirements

The CLI must accept:

```text
--platform
--program
--base-url
--roe-profile
--max-turns
--max-requests
--max-posts
--max-response-bytes
--root
```

The CLI must:

* require `--platform`
* require `--program`
* require `--base-url`
* load RoE profile from `--roe-profile`
* use safe default RoE if no profile is passed
* apply CLI limits as stricter overrides only (min of config and CLI)
* run existing gates before traffic
* load seed URLs from SQLite `signals`
* create `RoePolicy`
* create `ScopePolicy`
* create `RequestBudget`
* create `HttpTool` with base_url
* create `HackerSession` and seed URLs
* create `FindingVerifier` with RoE profile
* create provider from environment
* run `HackerLoop`
* print summary
* print verified findings first
* print candidate findings second
* print policy denials
* return non-zero on gate failure

## Seed query

```sql
SELECT DISTINCT target
FROM signals
WHERE tool IN ('katana', 'swagger')
LIMIT 100
```

If no rows are found, seed with `base_url`.

## CLI name

Use:

```text
probe-target
```

## Example

```bash
bin/probe-target \
  --platform hackerone \
  --program example-program \
  --base-url https://target.example.com \
  --roe-profile roe/hackerone-example.yaml \
  --max-turns 20 \
  --max-requests 80
```

## Output

```text
probe-target: 9 turns, 3 candidates, 1 verified, 2 denials, stop=done
  [verified:idor] /api/users/999
  [candidate:debug_endpoint] /actuator/env
  [candidate:unsafe_redirect] /redirect?next=...
  [denied] rate_limit_test denied by RoE profile
```

## Tests

Cover:

* missing base URL raises `SystemExit`
* missing RoE profile uses safe default
* custom RoE profile loads
* CLI overrides limits only in stricter direction
* gate failure returns non-zero
* CLI seeds from DB
* CLI falls back to base URL
* CLI prints verified findings
* CLI prints candidate findings
* CLI prints policy denials
* CLI returns `0` on success

## Shell entry point

```sh
#!/bin/sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/python" -m earn_money.agent.hacker_loop_cli --root "$ROOT" "$@"
```

Then:

```bash
chmod +x bin/probe-target
```

## Acceptance

```bash
pytest tests/agent/test_hacker_loop_cli.py -v
```

Commit:

```bash
git add src/earn_money/agent/hacker_loop_cli.py tests/agent/test_hacker_loop_cli.py bin/probe-target
git commit -m "feat(agent): add RoE-aware probe CLI"
```
