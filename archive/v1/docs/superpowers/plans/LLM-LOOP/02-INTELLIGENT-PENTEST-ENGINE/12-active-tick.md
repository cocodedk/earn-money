# Task 12: Wire into active tick CLI

## Modify

```text
src/earn_money/engine/active_tick_cli.py
tests/engine/test_active_tick_cli.py
```

## Requirements

Add:

```python
parser.add_argument(
    "--hack",
    metavar="BASE_URL",
    help="run the RoE-controlled LLM probe loop against BASE_URL",
)

parser.add_argument(
    "--roe-profile",
    help="path to YAML RoE profile for the LLM probe loop",
)
```

Before the normal active pipeline:

```python
if args.hack:
    from earn_money.agent import hacker_loop_cli

    cli_args = [
        "--platform", args.platform or "local",
        "--program", args.program or "",
        "--base-url", args.hack,
        "--root", str(args.root),
    ]

    if args.roe_profile:
        cli_args.extend(["--roe-profile", args.roe_profile])

    return hacker_loop_cli.main(cli_args)
```

## Tests

Cover:

* `--hack` calls `hacker_loop_cli.main`
* normal active pipeline does not run when `--hack` is present
* RoE profile is passed through
* platform, program, base URL, and root are passed correctly

## Acceptance

```bash
pytest tests/engine/test_active_tick_cli.py -v
```

Commit:

```bash
git add src/earn_money/engine/active_tick_cli.py tests/engine/test_active_tick_cli.py
git commit -m "feat(engine): wire RoE-controlled probe loop into active tick"
```
