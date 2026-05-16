# Task 3: Add scope policy

## Create

```text
src/earn_money/agent/scope_policy.py
tests/agent/test_scope_policy.py
```

## Requirements

`ScopePolicy` must:

* use `RoeProfile.allowed_hosts`
* use `RoeProfile.denied_hosts`
* allow relative paths under the base URL
* allow absolute URLs only when host is in scope
* reject denied hosts
* reject unsupported schemes
* reject path traversal
* reject private, loopback, link-local, multicast, and metadata IPs unless RoE explicitly allows them
* reject redirects to out-of-scope hosts
* normalize URLs
* raise `ScopeDenied` with a clear reason

## Tests

Cover:

* relative path resolves under base URL
* same-host absolute URL is allowed
* allowed wildcard host is allowed
* denied wildcard host is rejected
* external host is rejected
* unsupported scheme is rejected
* path traversal is rejected
* localhost is rejected by default
* `127.0.0.1` is rejected by default
* `169.254.169.254` is rejected by default
* same-host redirect is allowed
* external redirect is rejected

## Acceptance

```bash
pytest tests/agent/test_scope_policy.py -v
```

Commit:

```bash
git add src/earn_money/agent/scope_policy.py tests/agent/test_scope_policy.py
git commit -m "feat(agent): add scope policy from RoE"
```
