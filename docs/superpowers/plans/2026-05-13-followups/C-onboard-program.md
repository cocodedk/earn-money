# C — Onboard a fresh low-density H1 program

**Problem:** `hackerone/security` is real-target validation but
near-100% dupe rate. Next session needs a program where new findings
have a realistic chance of being non-dup.

**Solution:** Pick one HackerOne public program meeting the design
spec's selection criteria, write its `scope.md`, sync, ready for
nightly cron in the next session.

## Selection criteria (from the parent design spec)

- `rate-limited-OK` policy (automated scanning explicitly permitted).
- Low researcher density (NOT Shopify/HackerOne/Twitter/Yahoo class).
- Cash bounties (not just swag/rep).
- Asset class operator knows (web/API preferred).
- Active program (resolved reports in the last 90 days).

## Steps

- [ ] **1. Research candidates via cursor**

```bash
cursor-agent --mode ask --print --model gpt-5.3-codex-high "List 3 public HackerOne programs that match: rate-limited-OK or equivalent (automated scanning permitted per policy), cash bounties (not just swag), low researcher density (skip well-known: Shopify, HackerOne, Mail.ru, GitLab, Yahoo, Verizon, Snap, Twitter, GitHub), prefer web/API asset class. For each: slug, public policy URL, approximate bounty range, scope summary, why you think researcher density is low. Bias toward small-to-mid B2B SaaS or smaller government VDPs with cash. Be specific — slugs from hackerone.com/<slug>."
```

- [ ] **2. Operator picks one**

Notify the operator on chat with the cursor list + one recommended
pick + rationale. Wait for `chat_ask` response. Do NOT proceed
without the operator's explicit pick.

- [ ] **3. Create `programs/hackerone/<slug>/scope.md`**

Use the existing `programs/hackerone/security/scope.md` as the
template. Fill in: `platform: hackerone`, `slug: <chosen>`,
`policy: rate-limited-OK` (verify from the program's policy page),
`in_scope: []`, `out_of_scope: []`, `scope_hash: pending`,
`last_synced: pending`, body `# <slug>` + one-paragraph operator note.

- [ ] **4. Run scope-sync locally to populate**

```bash
.venv/bin/python -m earn_money.runners.scope_sync --program <slug>
```

Verify it populates `in_scope`, `out_of_scope`, `scope_hash`,
`last_synced`.

- [ ] **5. `make smoke`** — green (the new program shouldn't break tests).

- [ ] **6. Commit:** `feat(programs): onboard hackerone/<slug> as low-density earnings target`.

- [ ] **7. CodeRabbit review:** `coderabbit review --agent -t committed --base HEAD~1`. Apply valid findings.

- [ ] **8. Rsync to VPS** (same flag set used elsewhere in this session)

```bash
rsync -a --delete \
  --exclude='.venv/' --exclude='__pycache__' --exclude='.git/' \
  --exclude='.env' --exclude='*.sqlite' --exclude='recon/outputs/' \
  --exclude='RECON_ENABLED' --exclude='.claude/' --exclude='.mcp.json' \
  --exclude='.ruff_cache' --exclude='.pytest_cache' --exclude='.mypy_cache' \
  /home/cocodedk/0-projects/earn-money/ recon-vps:/opt/earn-money/
```

- [ ] **9. Notify operator on chat** that the new program is loaded
  and ready for the next session's cron / on-demand recon run. Do NOT
  trigger active recon against it from this session — that's an
  explicit operator decision after they confirm scope/policy is what
  they expected.
