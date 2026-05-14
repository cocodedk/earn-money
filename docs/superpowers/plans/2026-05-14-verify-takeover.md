# `bin/verify-takeover` — ownership-check CLI

**Goal:** Operator-triggered helper that checks whether a takeover
finding's claimed target (GitHub org/user, for now) is already
claimed by the program owner. Prints a verdict + recommended action.
No engine integration; manual run per finding.

**Architecture:** One small CLI module. GitHub claim-check via
`https://api.github.com/users/<name>` (200 = claimed, 404 = unclaimed,
other = indeterminate). httpx is already a dep.

**Anti-goals:** no auto-routing into `_resolved/info/` (operator
decides), no support for non-GitHub takeover providers in v1, no
target-affiliation check (just "claimed?"; the operator reads the
returned org/blog/location and decides if it belongs to the target).

## TDD steps

- [ ] **1. Failing test — claimed org returns 0 + "CLAIMED" verdict**

```python
def test_verify_takeover_claimed_org(
    tmp_repo, capsys, mocker,
) -> None:
    paths = engine_paths(tmp_repo)
    fh = "f" * 64
    _insert_takeover(paths, fh, extracted="hacker0x01.github.io")
    mocker.patch.object(
        verify_takeover_cli, "_github_user_lookup",
        return_value=(200, {"login": "Hacker0x01", "type": "Organization",
                            "name": "HackerOne", "blog": "https://www.hackerone.com"}),
    )
    rc, out, _ = _run(paths.root, ["--program", "example", fh[:8]], capsys)
    assert rc == 0
    assert "CLAIMED" in out
    assert "Hacker0x01" in out
    assert "Organization" in out
```

- [ ] **2. Failing test — unclaimed (404) returns 0 + "UNCLAIMED" verdict.**

- [ ] **3. Failing test — indeterminate (network error or unexpected status)
  returns 0 + "INDETERMINATE" verdict + suggestion to retry.**

- [ ] **4. Failing test — non-takeover finding returns 1 + error.**

- [ ] **5. Failing test — unknown hash prefix returns 1 (mirror bin/show).**

- [ ] **6. Failing test — unregistered program returns 1 + "not registered".**

- [ ] **7. Implement `src/earn_money/triage/verify_takeover_cli.py`:**

  - Args: `--platform`, `--program`, `--root`, positional `prefix`.
  - Validate scope.md exists.
  - Resolve prefix via the same LIKE-escape logic as `bin/show`.
  - Validate `vuln_class` contains "takeover" (refuse otherwise).
  - Parse the signal payload to extract the target hostname
    (`payload.extracted` for github-takeover).
  - Extract org/user from the hostname (`<name>.github.io` → `<name>`).
  - `_github_user_lookup(name)` → `(status_code, body_dict_or_empty)`.
  - Print verdict block + recommended transition_state snippet.

- [ ] **8. `bin/verify-takeover`** sh wrapper. `chmod +x`.

- [ ] **9. `make smoke`** green.

- [ ] **10. Commit** as `feat(bin): verify-takeover ownership-check CLI`.

- [ ] **11. CodeRabbit review.** Apply valid findings.

- [ ] **12. Run on the real finding** `f5df5f0d` against the live
  `hacker0x01.github.io` lookup to validate end-to-end. Capture output
  in the engagement gap log.
