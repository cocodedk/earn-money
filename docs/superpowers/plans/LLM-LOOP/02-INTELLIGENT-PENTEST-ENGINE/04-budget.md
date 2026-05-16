# Task 4: Add request budget

## Create

```text
src/earn_money/agent/budget.py
tests/agent/test_budget.py
```

## Requirements

`RequestBudget` must be built from `RoeProfile`.

It must track:

* max turns
* max total requests
* max POST requests
* max response bytes retained
* max runtime seconds
* delay between requests

It must expose:

```python
check_turn(turn: int) -> None
check_request(method: str) -> None
record_request(method: str) -> None
truncate_body(body: str) -> str
sleep_if_needed() -> None
```

It must raise `BudgetExceeded` when limits are crossed.

## Tests

Cover:

* request under limit allowed
* request over limit blocked
* POST over limit blocked
* turn over limit blocked
* body is truncated
* runtime limit blocks execution
* delay function is called when configured

## Acceptance

```bash
pytest tests/agent/test_budget.py -v
```

Commit:

```bash
git add src/earn_money/agent/budget.py tests/agent/test_budget.py
git commit -m "feat(agent): add RoE-based request budget"
```
