# Task 13: Full test pass

Run:

```bash
pytest tests/agent -v
pytest tests/engine/test_active_tick_cli.py -v
pytest -q
```

Fix failures.

Commit:

```bash
git add .
git commit -m "test(agent): stabilize RoE-controlled probe loop"
```
