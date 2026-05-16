# Task 1: Add RoE profile

## Create

```text
src/earn_money/agent/roe_profile.py
tests/agent/test_roe_profile.py
```

## Requirements

`RoeProfile` must support:

* allowed hosts
* denied hosts
* allowed methods
* traffic limits
* test permissions
* evidence rules
* profile name
* source metadata

The source metadata should allow tracking where the RoE came from:

```python
source_type: Literal["client_contract", "hackerone", "bug_bounty", "internal_lab", "manual"]
source_ref: str | None
```

## Required fields

```python
name: str
allowed_hosts: list[str]
denied_hosts: list[str]
max_requests: int
max_posts: int
max_turns: int
max_runtime_seconds: int
max_response_bytes: int
delay_between_requests_ms: int

allow_get: bool
allow_post: bool
allow_put: bool
allow_patch: bool
allow_delete: bool

allow_authenticated_testing: bool
allow_rate_limit_testing: bool
allow_bruteforce: bool
allow_password_spraying: bool
allow_credential_stuffing: bool
allow_exploit_chains: bool
allow_destructive_actions: bool
allow_file_upload_tests: bool
allow_graphql_introspection: bool
allow_openapi_probing: bool
allow_idor_checks: bool
allow_xss_probe_payloads: bool
allow_sqli_probe_payloads: bool

require_replay_steps: bool
require_non_destructive_poc: bool
allow_sensitive_data_capture: bool
max_evidence_body_bytes: int
```

## Tests

Cover:

* default safe profile loads
* custom YAML profile loads
* missing allowed hosts fails
* negative request limits fail
* unknown fields fail
* permissions default to safe values
* source metadata is stored

## Acceptance

```bash
pytest tests/agent/test_roe_profile.py -v
```

Commit:

```bash
git add src/earn_money/agent/roe_profile.py tests/agent/test_roe_profile.py
git commit -m "feat(agent): add RoE profile model"
```
