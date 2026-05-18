# Task 9: Add finding verifier

## Create

```text
src/earn_money/agent/finding_verifier.py
tests/agent/test_finding_verifier.py
```

## Requirements

Findings must start as candidates.

A finding becomes verified only when the verifier has enough evidence under the current RoE.

`FindingVerifier` must be initialized with `RoeProfile` to check permissions.

For v1, implement:

```text
IDOR candidate detection
exposed debug endpoint candidate detection
token leak candidate detection
unsafe redirect candidate detection
```

## IDOR candidate

Create candidate when:

* action is GET
* response status is `200`
* path ends in numeric ID
* body contains user-like fields such as `email`, `role`, `user_id`, or `id`

Promote to verified when:

* active user ID is known
* requested object ID differs from active user ID
* body contains user-like data
* replay steps can be produced
* RoE allows IDOR checks (`allow_idor_checks: true`)

## Debug endpoint candidate

Create candidate when:

* path contains `/debug`, `/actuator`, `/env`, `/phpinfo`, `/server-status`, or similar
* response status is `200`
* body contains environment, stack, config, or secret-like markers

Promote only if evidence is non-destructive and does not require dumping excessive sensitive data.

## Token leak candidate

Create candidate when:

* response contains token-like values (JWT, API key pattern)
* evidence body is truncated according to RoE
* sensitive capture is allowed or token is masked

By default, mask leaked values in output.

## Unsafe redirect candidate

Create candidate when:

* app reflects a user-controlled redirect parameter
* response redirects to an attacker-controlled URL
* redirect behavior is confirmed without leaving scope

## Methods

```python
def evaluate(
    self,
    action: dict,
    observation: ObservationWrapper,
    session: HackerSession,
) -> tuple[list[dict], list[dict]]:
    """Returns (new_candidates, new_verified_findings)"""
```

## Tests

Cover:

* IDOR candidate created
* IDOR not created for non-numeric path
* IDOR not created for non-200
* IDOR promoted only with active user ID and RoE permission
* debug endpoint candidate created
* token leak candidate masks token
* unsafe redirect candidate created
* candidate not promoted without replay steps
* verified finding includes replay steps
* RoE denial prevents promotion

## Acceptance

```bash
pytest tests/agent/test_finding_verifier.py -v
```

Commit:

```bash
git add src/earn_money/agent/finding_verifier.py tests/agent/test_finding_verifier.py
git commit -m "feat(agent): add RoE-aware finding verifier"
```
