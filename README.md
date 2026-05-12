# earn-money

Private operations repo for a continuous bug-bounty pipeline built around `clawpwn`. Phase 2 (deferred): a self-serve FITS Express mini-audit product.

This repository is **private** and operational. It is not a published product. The contents include scope definitions, recon configuration, finding workflows, and report templates. Sensitive operational artefacts (raw recon outputs, identity, payout config, per-program SQLite state, the `RECON_ENABLED` kill-switch) are gitignored and live only on the operator's machine.

## Design

The full design is in [`docs/superpowers/specs/2026-05-12-earn-money-design.md`](docs/superpowers/specs/2026-05-12-earn-money-design.md). Hard rules are duplicated in [`CLAUDE.md`](CLAUDE.md).

Key invariants:

- Scope is gospel. No scan against an asset not in the current `scope.md`.
- Two human gates. No automated submission. Reports require substantive human edit.
- Three-tier program policy: `rate-limited-OK`, `manual-only`, `ambiguous`.
- `RECON_ENABLED` flag file is the master kill-switch.

## Local setup

Clone, then install the git hooks:

```bash
./scripts/install-hooks.sh
```

The `pre-push` hook is owner-locked to `github.com/cocodedk` — pushing this repo to any other GitHub owner will fail.

## Author

**Babak Bandpey** — [cocode.dk](https://cocode.dk) | [LinkedIn](https://linkedin.com/in/babakbandpey) | [GitHub](https://github.com/cocodedk)

## License

Apache-2.0 | © 2026 [Cocode](https://cocode.dk)
