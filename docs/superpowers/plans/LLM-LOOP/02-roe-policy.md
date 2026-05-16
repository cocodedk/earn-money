# Task 2: Add RoE policy engine

## Create

```text
src/earn_money/agent/roe_policy.py
tests/agent/test_roe_policy.py
```

## Requirements

`RoePolicy` decides whether an action is allowed by the current RoE.

It must check:

* HTTP method
* target host
* action type
* test category
* destructive behavior
* brute force behavior
* rate-limit behavior
* exploit-chain behavior
* evidence capture limits

The policy must return clear allow/deny results.

Example result:

```python
@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
```

## Action categories

Each action should have a category:

```text
recon
http_get
http_post
auth
idor_check
graphql_introspection
openapi_probe
rate_limit_test
bruteforce
xss_probe
sqli_probe
file_upload_test
exploit_chain
destructive
report_candidate
store_memory
stop
```

## Tests

Cover:

* GET allowed when profile allows GET
* POST denied when profile disables POST
* rate-limit test denied unless enabled
* brute force denied unless enabled
* exploit chain denied unless enabled
* destructive action denied unless enabled
* IDOR check allowed only when enabled
* GraphQL introspection allowed only when enabled
* unknown category denied
* denial reason is readable

## Acceptance

```bash
pytest tests/agent/test_roe_policy.py -v
```

Commit:

```bash
git add src/earn_money/agent/roe_policy.py tests/agent/test_roe_policy.py
git commit -m "feat(agent): add RoE policy engine"
```
