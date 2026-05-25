# Contributing

This is a private operational repository. The operator is the sole maintainer. Notes here exist so future Claude sessions and any future co-operator can pick up the workflow without re-learning it.

## Local setup

1. Clone the repository.
2. Install the git hooks once:
   ```bash
   ./scripts/install-hooks.sh
   ```
3. The `RECON_ENABLED` kill-switch is intentionally absent on fresh clones. To enable recon on this clone, create the file: `touch RECON_ENABLED`. Remove it (`rm RECON_ENABLED`) to halt all cron-driven recon immediately.
4. Sensitive operational state lives in gitignored paths:
   - `identity/platforms.md` — platform handles, payout config, VPS IP
   - `recon/outputs/` — raw recon artefacts
   - `programs/**/db.sqlite` — per-program asset and finding state
   - `.env`, `.envrc` — local environment overrides

## Hooks

Three hooks ship in `.githooks/` and are activated by the installer:

- **`pre-commit`** — blocks staged sensitive paths, then runs `./scripts/test.sh quick`
- **`commit-msg`** — enforces Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`, `build:`, `perf:`, `revert:`, `style:`)
- **`pre-push`** — owner-locked. Refuses any push to a remote whose URL is not under `github.com/cocodedk`. Stops accidents, not malice (`--no-verify` bypasses it by design).

## Branch naming

`<type>/<short-description>` in kebab-case. Type matches the Conventional Commit type used in the PR.

| Prefix | Commit type | Example |
|---|---|---|
| `feature/` | `feat:` | `feature/scope-sync` |
| `fix/` | `fix:` | `fix/freeze-flag-respect` |
| `chore/` | `chore:` | `chore/update-deps` |
| `docs/` | `docs:` | `docs/clarify-policy-tiers` |
| `refactor/` | `refactor:` | `refactor/runner-base-class` |
| `ci/` | `ci:` | `ci/add-shellcheck` |

Never commit directly to `main` once branch protection is enabled.

## Recommended local `git config`

Run once after cloning:

```bash
git config pull.rebase true
git config core.autocrlf input
git config push.autoSetupRemote true
git config init.defaultBranch main
```

## Operational reminders

The hard rules from [`CLAUDE.md`](CLAUDE.md) override anything written here. If something in this file ever conflicts with `CLAUDE.md`, `CLAUDE.md` wins.
