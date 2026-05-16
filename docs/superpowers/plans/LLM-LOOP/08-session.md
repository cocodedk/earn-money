# Task 8: Add structured session memory

## Create or replace

```text
src/earn_money/agent/session.py
tests/agent/test_session.py
```

## Requirements

Session memory must separate facts from guesses.

Use fields:

```python
tokens: dict[str, str]           # raw token values (never shown in prompt)
ids: dict[str, str]              # discovered IDs
urls: list[str]                  # discovered URLs
observations: list[ObservationWrapper]  # from Task 6
hypotheses: list[str]
candidate_findings: list[dict]
verified_findings: list[dict]
turn_log: list[str]
policy_denials: list[str]
```

The session must support:

```python
store_token(key: str, value: str) -> None
get_token(key: str) -> str | None
store_id(key: str, value: str) -> None
seed_urls(urls: list[str]) -> None
add_observation(obs: ObservationWrapper) -> None
add_hypothesis(hypothesis: str) -> None
add_candidate_finding(finding: dict) -> None
add_verified_finding(finding: dict) -> None
add_policy_denial(reason: str) -> None
log_turn(action: dict, result: str) -> None
summary() -> dict
prompt_view() -> str
```

`prompt_view()` must avoid leaking raw secrets into the prompt.

For tokens, include token names only:

```text
tokens: ["access", "refresh"]
```

Do not include raw token values.

For observations, call `obs.to_prompt()` for each.

## Tests

Cover:

* token storage
* token names only in prompt view (values not visible)
* ID storage
* URL dedupe
* observation storage (wrapped)
* hypothesis storage
* candidate finding storage
* verified finding storage
* policy denial storage
* turn logging
* summary counts

## Acceptance

```bash
pytest tests/agent/test_session.py -v
```

Commit:

```bash
git add src/earn_money/agent/session.py tests/agent/test_session.py
git commit -m "feat(agent): add structured session memory with untrusted observations"
```
