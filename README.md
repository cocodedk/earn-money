# earn-money

Public operational repository for a continuous bug-bounty pipeline.

## Status — v2 fresh start (2026-05-18)

The v1 corpus — full pipeline built around `clawpwn`, with recon runners, agent, dashboard, triage, and reporting — is parked under [`archive/v1/`](archive/v1/). Tag `v1-final` marks its complete state; nothing was deleted.

The active direction is the [**vuln-scanning cookbook**](docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/): 278 leaf-bullet specs across 24 phases of OWASP / PortSwigger coverage, each filled in by GPT-5.5 enrichment then implemented in TDD against local fixtures on `target.cocode.dk`.

## Direction

- **Deterministic first.** AI is not the automation layer. Reach for AI only when no deterministic option fits the bullet's intent — and the spec's `## AI involvement` section names that gap.
- **Paste-ready contract.** Every spec stub carries an enrichment-zone marker telling GPT-5.5 what's protected (frontmatter, title, blockquote, `##` headings) and what's editable (body under each section).
- **Shared schema.** Cross-cutting `ScanTarget` and `Evidence` live once in [`00-shared-schema.md`](docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md); stubs define only their domain-specific `<X>Signature` / `<X>Finding`.
- **One phase at a time.** A phase ships only when every spec is `done` AND every plan is `verified`.

## Layout

```
docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/  ← Cookbook specs (278 stubs, 24 phases)
docs/superpowers/plans/2026-05-18-VULN-SCANNING-COOKBOOK/   ← Mirror plan tree
scripts/cookbook_progress.py                                ← Reads frontmatter → PROGRESS.md
scripts/cookbook_bootstrap.py                               ← Idempotent migrator (--apply to write)
scripts/cookbook_templates.py                               ← Templates + section schemas
archive/v1/                                                 ← Parked v1 corpus
CLAUDE.md                                                   ← Operational rules
```

## Test fixtures

Operator-owned vuln-app host at `target.cocode.dk` (`89.167.63.167`). Four endpoints behind Caddy, all HTTPS:

| URL | App | Default access |
|-----|-----|----------------|
| `https://target.cocode.dk/` | OWASP Juice Shop | "Mystery" blind target — runners fingerprint; no hostname/path leak. |
| `https://juiceshop.cocode.dk/` | OWASP Juice Shop | Same container, identifiable hostname. |
| `https://dvwa.cocode.dk/` | DVWA | `admin` / `password`. DB auto-created via MariaDB sidecar (`dvwa-db` on docker network `dvwa-net`). |
| `https://webgoat.cocode.dk/` | WebGoat | Root → `/WebGoat/login`. Self-service registration. |

All four URLs are authorised for any HTTP technique; the `roe.md` floor in [`CLAUDE.md`](CLAUDE.md) applies only to live programs. SSH: `root@target.cocode.dk` with `~/.ssh/id_cocodedk`.

## Cookbook workflow

1. **Spec.** GPT-5.5 enriches a stub. Operator reviews; flips spec `status:` to `done` and assigns `fixture:`.
2. **Plan.** Once the spec is `done`, draft the matching plan at the mirror path under `docs/superpowers/plans/...`; walk plan `status:` through `drafted → approved → implemented → verified`.
3. **Implement.** TDD per the plan against the assigned fixture URL.
4. **Persist.** Each runner writes findings into shared `ScanTarget` + `Evidence` plus its own `<X>Signature` / `<X>Finding`.
5. **Regenerate `PROGRESS.md`** with `python scripts/cookbook_progress.py` and commit.

See the [cookbook README](docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/README.md) for the full workflow + frontmatter contract.

## v1 reference

To run the v1 pipeline from its archived state:

```bash
cd archive/v1
make smoke      # the v1 lint + mypy + tests (1018 tests)
```

Project-wide invariants survive from v1 (scope is gospel, two human gates, three-tier program policy, `RECON_ENABLED` kill-switch). The current [`CLAUDE.md`](CLAUDE.md) preserves them; [`archive/v1/CLAUDE.md`](archive/v1/CLAUDE.md) carries the full original text.

## Local setup

```bash
./scripts/install-hooks.sh    # one-time: pre-commit + pre-push + commit-msg
```

The pre-push hook is owner-locked to `github.com/cocodedk`. The pre-commit hook refuses sensitive paths (RECON_ENABLED, *.sqlite, identity/platforms.md, recon/outputs/, .env) at both root and `archive/v1/` mirrors.

For the cookbook scripts, any Python 3.12+ with `python-frontmatter` works. The existing `.venv/` at repo root (built from the v1 `pyproject.toml`) already has the dep:

```bash
.venv/bin/python scripts/cookbook_progress.py    # regenerate PROGRESS.md
.venv/bin/python scripts/cookbook_bootstrap.py   # dry-run preview
.venv/bin/python scripts/cookbook_bootstrap.py --apply   # apply migrations
```

When cookbook-v2 code lands, the venv will be rebuilt from a new root-level `pyproject.toml`. Until then, the v1 venv suffices for the scripts.

## Author

**Babak Bandpey** — [cocode.dk](https://cocode.dk) | [LinkedIn](https://linkedin.com/in/babakbandpey) | [GitHub](https://github.com/cocodedk)

## License

Apache-2.0 | © 2026 [Cocode](https://cocode.dk)
