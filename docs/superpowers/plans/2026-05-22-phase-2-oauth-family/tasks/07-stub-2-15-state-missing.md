# Task 07 — Stub 2.15: oauth-missing-state detection chain

Implement the detection logic in `oauth_missing_state/`. The skeleton runner and gate tests
already exist. This task is split into two parts: the classification helper and its unit tests,
then the runner integration and end-to-end tests.

**Depends on:** Task 02, Task 06 (fixture running)

## Sub-tasks

- [07a-classify.md](07a-classify.md) — Steps 1–4: `test_classify.py` + `classify.py`
- [07b-runner.md](07b-runner.md) — Steps 5–9: `test_runner.py` + detection chain in `runner.py` + coverage + commit
