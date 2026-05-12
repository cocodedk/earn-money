# Programs

One subdirectory per onboarded program: `programs/<platform>/<slug>/`.

## Prerequisites

Before running the onboarding flow below, install the Python dev environment once:

    make install-dev

This creates the `.venv` that `bin/scope-sync` invokes. If you run `bin/scope-sync` without this step, it exits 1 with a hint message.

## Onboarding a new HackerOne program — operator workflow

1. **Pick the program.** Criteria from the design spec: low researcher density, asset class you know well, ToS permits the desired scanning tier.

2. **Decide the policy tier.** Read the program's ToS carefully:
   - `rate-limited-OK` — automated scanning permitted within rate limits. Full pipeline.
   - `manual-only` — automated scanning prohibited. Operator scans by hand; recon runners refuse to start.
   - `ambiguous` — ToS unclear. Send a written clarification request; record the reply in `programs/hackerone/<slug>/notes.md`. Use `ambiguous` until the program replies; passive recon only.

3. **Create the program directory and seed `scope.md`** (replace `<slug>` with the program handle):

   ```bash
   mkdir -p programs/hackerone/<slug>
   cat > programs/hackerone/<slug>/scope.md <<'EOF'
   ---
   platform: hackerone
   slug: <slug>
   policy: rate-limited-OK
   scope_hash: ""
   last_synced: ""
   in_scope: []
   out_of_scope: []
   ---

   # <slug>

   Operator notes go here.
   EOF
   ```

4. **Set credentials** in the untracked `.env` file at the repo root (gitignored — never commit):

   ```
   HACKERONE_API_USERNAME="<your handle>"
   HACKERONE_API_TOKEN="hai_xxxxxxxxxxxxxxxx"
   ```

5. **Enable recon** with `touch RECON_ENABLED` (also gitignored).

6. **First sync** to populate the scope from the HackerOne API:

   ```bash
   bin/scope-sync --program <slug>
   ```

   Expected output: `scope-sync: updated — scope updated, hash=<12-char hash>`.

7. **Inspect** `programs/hackerone/<slug>/scope.md`. The `in_scope` and `out_of_scope` lists should now reflect the program's structured scope.

## What happens on subsequent syncs

- No change → `unchanged` action, only `last_synced` is updated.
- New assets added by the program → `updated` action, `scope.md` rewritten.
- Assets removed from in-scope → `frozen` action. A `FROZEN` file is written in the program directory with the reason. Recon for that program halts until the operator reviews the diff and removes `FROZEN`.
- `RECON_ENABLED` absent → `scope-sync` exits 2 with a message on stderr and does not touch any program state. Re-create the flag (`touch RECON_ENABLED`) to resume.

## Resuming after a freeze

1. Inspect the diff yourself in the HackerOne program page.
2. Update `programs/hackerone/<slug>/scope.md` to match the new scope (or leave as-is if the removed asset wasn't being scanned).
3. Delete the `FROZEN` file: `rm programs/hackerone/<slug>/FROZEN`.
4. Re-run `bin/scope-sync --program <slug>` to confirm a clean sync.

## Passive recon (Phase 2)

After `bin/scope-sync` has populated the program's in-scope list, you can run passive recon to discover subdomains and persist them in the program's SQLite store.

### Prerequisites (one-time per VPS)

- Install `subfinder`:
  ```bash
  go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
  ```
  Verify with `subfinder -version`.
- Add a Chaos API token to `.env`:
  ```
  CHAOS_API_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  ```

### Run

```bash
bin/passive-recon --program <slug>
```

Optional flags:

- `--resolver 1.1.1.1` (repeatable) — pick the recursive DNS resolvers. Defaults to `1.1.1.1` and `9.9.9.9`. On a production VPS, prefer a dedicated or self-hosted resolver to avoid leaking enumeration patterns to your hosting provider's DNS.

### Output

Stdout: `passive-recon: discovered=<n> upserted=<n>`.

The per-program SQLite database at `programs/hackerone/<slug>/db.sqlite` now contains rows in the `assets` table — one per discovered, in-scope subdomain, with `first_seen`, `last_seen`, comma-joined `ip`, and `in_scope_at_observation`. This file is gitignored; do not commit it.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Unexpected error (network, Chaos credentials missing, etc.) |
| 2 | `RECON_ENABLED` absent |
| 3 | Program is frozen — review `programs/hackerone/<slug>/FROZEN`, fix, and remove |
| 4 | Policy violation — the program is `manual-only` and refuses automated recon |

### What does NOT happen in Phase 2

- No HTTP probing. `httpx` against the discovered subdomains is Phase 3.
- No daily digest. `ops/daily-digest.md` is Phase 3.
- No active recon (nuclei, katana, ffuf). Phase 3+.
