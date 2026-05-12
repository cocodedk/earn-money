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
