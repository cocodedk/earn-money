# Operator Follow-ups: scope-sync cron, IPv4-only egress, second BBP

> **For agentic workers:** REQUIRED SUB-SKILL — `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the three operator-level items left over from 2026-05-15 — fix the broken scope-sync cron, lock VPS egress to IPv4, onboard a second low-density BBP. Three independent tasks, ordered below. Stack: sh, systemd, Linux networking, HackerOne API.

---

### Task 1: Scope-sync cron fix (two parts)

**Root cause A (bug):** `bin/scope-sync` requires `--program` (argparse `required=True`). `scripts/passive-tick.sh:28` invokes it with no args. argparse exits with code 2, the `|| warn` swallows the error, the daily timer reports green, `scope.last_synced` never refreshes.

**Root cause B (rule violation):** Spec line 103 + CLAUDE.md require: "If scope sync fails or detects a destructive diff, recon for that program freezes until the operator acks." `scope_sync.py` today freezes only on destructive diff (lines 64–72) — not on API/network/auth failures. The wrapper script swallows the non-zero exit and the rule is silently bypassed.

**Files:**
- Modify: `scripts/passive-tick.sh:27-28` (Part A)
- Modify: `src/earn_money/runners/scope_sync.py` (Part B)
- Test: `tests/runners/test_scope_sync.py` — add a freeze-on-API-failure case.

#### Part A — iterate programs from the tick script

- [ ] **Step 1:** Replace lines 27-28 with a per-program loop that mirrors the passive-recon iteration at lines 31-44:

```sh
log "scope-sync (per program)"
find "$ROOT/programs" -mindepth 2 -maxdepth 2 -type d | while read -r prog_dir; do
    slug="$(basename "$prog_dir")"
    platform="$(basename "$(dirname "$prog_dir")")"
    [ -f "$prog_dir/scope.md" ] || continue
    if [ -f "$prog_dir/FROZEN" ]; then
        warn "  $platform/$slug FROZEN — skipping"
        continue
    fi
    log "  scope-sync $platform/$slug"
    "$ROOT/bin/scope-sync" --platform "$platform" --program "$slug" \
        || warn "    exit non-zero — runner is responsible for freezing"
done
```

#### Part B — freeze on any sync failure inside the runner

- [ ] **Step 2:** Write two failing tests in `tests/runners/test_scope_sync.py`:
  - `test_api_failure_freezes_program` — stub the HackerOne client's `fetch_structured_scope` to raise; assert `main([...])` returns non-zero AND `paths.freeze_flag(platform, slug).exists()` is True AND the freeze reason contains "scope-sync failed".
  - `test_missing_credentials_freezes_program` — clear `HACKERONE_API_TOKEN` and `HACKERONE_API_USERNAME`; assert the same three things. This exercises the path where `hackerone.Client(...)` construction or first call raises before `sync_program()` is reached.
- [ ] **Step 3:** In `scope_sync.main()`, restructure the existing try/except/finally:

  ```python
  client = None
  try:
      client = hackerone.Client(
          username=os.environ.get("HACKERONE_API_USERNAME", ""),
          token=os.environ.get("HACKERONE_API_TOKEN", ""),
      )
      result = sync_program(paths, args.platform, args.program, client)
  except (flags.ReconDisabled, flags.ProgramFrozen) as e:
      print(f"scope-sync: {e}", file=sys.stderr)
      return 2 if isinstance(e, flags.ReconDisabled) else 3
  except Exception as e:
      flags.freeze_program(
          paths, args.platform, args.program,
          reason=f"scope-sync failed: {type(e).__name__}: {e}",
      )
      print(f"scope-sync: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
      return 1
  finally:
      if client is not None:
          client.close()
  ```
  The destructive-diff freeze inside `sync_program()` is unchanged.
- [ ] **Step 4:** Run `pytest tests/runners/test_scope_sync.py -v` — all green.

#### Smoke + deploy + verify

- [ ] **Step 5:** Do NOT run `bash scripts/passive-tick.sh` locally — it invokes `passive-recon` which does live DNS against scoped assets from the laptop's IP. Dry-run only the loop logic:
  ```sh
  find programs -mindepth 2 -maxdepth 2 -type d | while read -r prog_dir; do
      slug="$(basename "$prog_dir")"; platform="$(basename "$(dirname "$prog_dir")")"
      [ -f "$prog_dir/scope.md" ] || continue
      [ -f "$prog_dir/FROZEN" ] && continue
      echo "would run: bin/scope-sync --platform $platform --program $slug"
  done
  ```
  Expected: two `would run:` lines. Full integration runs on the VPS in Step 8.
- [ ] **Step 6:** Force-fail path against a throwaway program (so `security`/`algolia` audit history stays clean). `RECON_ENABLED` must be present or the runner exits with `ReconDisabled` before bad creds are exercised — script handles this with snapshot + trap:
  ```sh
  HAD_RECON_FLAG=0; [ -f RECON_ENABLED ] && HAD_RECON_FLAG=1
  trap 'rm -rf programs/hackerone/_smoke; [ "$HAD_RECON_FLAG" = "0" ] && rm -f RECON_ENABLED' EXIT INT TERM

  mkdir -p programs/hackerone/_smoke
  cp programs/hackerone/security/scope.md programs/hackerone/_smoke/
  cp programs/hackerone/security/roe.md programs/hackerone/_smoke/
  # edit programs/hackerone/_smoke/scope.md: slug=_smoke, bogus platform_program_id

  touch RECON_ENABLED
  HACKERONE_API_TOKEN=invalid_force_fail HACKERONE_API_USERNAME=invalid \
      .venv/bin/python -m earn_money.runners.scope_sync \
      --platform hackerone --program _smoke --root . || true

  test -f programs/hackerone/_smoke/FROZEN && cat programs/hackerone/_smoke/FROZEN
  ```
  Do not commit any of these files.
- [ ] **Step 7:** Push to VPS: `bash scripts/sync-vps.sh`.
- [ ] **Step 8:** Trigger the timer one-shot on the VPS:
  `ssh recon-vps 'systemctl start earn-money-passive-tick.service && journalctl -u earn-money-passive-tick.service -n 80 --no-pager'`.
- [ ] **Step 9:** Verify `last_synced` is fresh:
  `ssh recon-vps "grep last_synced /opt/earn-money/programs/hackerone/*/scope.md"` — both timestamps within the last minute.
- [ ] **Step 10:** Commit:
  `git commit -m "fix(passive-tick): iterate programs for scope-sync; freeze on any sync failure"`

---

### Task 2: IPv4-only egress lock-down

**Decision (operator-approved):** outbound traffic uses `178.105.140.53` only. Drop the `2a01:4f8:1c18:908b::1` global IPv6 route, disable RA / DHCPv6 / link-local on the egress interface so the route can't come back unannounced.

**Why it matters:** every active runner that touches a target needs a stable, attributable egress. Dual-stack lets a route silently flip mid-scan; HackerOne triagers cross-reference IPs. One IP, one identity.

**Files (on the VPS, not the repo):**
- `/etc/netplan/*.yaml` — drop the v6 `addresses:` and `gateway6:` entries on the egress interface.
- `docs/superpowers/specs/2026-05-12-earn-money-design.md` — name the IPv4 egress address and state "no IPv6 egress" in the egress section.

- [ ] **Step 1:** Snapshot current state: `ssh recon-vps 'ip -6 addr show; ip -6 route; cat /etc/netplan/*.yaml'`.
- [ ] **Step 2:** Edit the netplan yaml on the egress interface stanza. Remove static v6 *and* lock the interface against RA/DHCPv6 (otherwise the provider can re-add a route silently):
  ```yaml
  # remove: addresses: starting "2a01:..." and any gateway6: line
  # add to the interface:
  accept-ra: false
  dhcp6: false
  link-local: []   # drop IPv6 link-local too — defence in depth
  ```
- [ ] **Step 3:** `netplan try` (auto-reverts on 120s if SSH dies). If SSH survives the prompt, accept; otherwise re-edit and try again.
- [ ] **Step 4:** `netplan apply` to persist.
- [ ] **Step 5:** Verify the three independent invariants:
  ```sh
  ssh recon-vps 'ip -6 addr show scope global'         # expected: empty
  ssh recon-vps 'ip -6 route show default'             # expected: empty
  ssh recon-vps 'curl -4 -s https://ipv4.icanhazip.com'  # expected: 178.105.140.53
  ssh recon-vps 'curl -6 -s --max-time 5 https://ipv6.icanhazip.com; echo exit=$?' # expected: non-zero, no output
  ```
  If any check fails, the v6 path is still alive — investigate before declaring Task 2 done.
- [ ] **Step 6:** Update the design doc's egress section — one paragraph stating the v4 address and the no-v6 decision.
- [ ] **Step 7:** Commit the doc change: `git commit -m "docs: lock VPS egress to IPv4-only (decision 2026-05-15)"`.

---

### Task 3: Second low-density BBP onboard

**Phase gate (spec lines 220–222):** Phase 4 program count is one; new programs onboard only during Phase 5, *and only after the existing pipeline is proven clean*. Confirm the Phase 5 gate before any onboarding step:

- [ ] **Step 0 (precondition gate):** All four must hold before this task is allowed to start. If any fails, park the task.
  - `findings/_queue/` has no items older than 7 days untouched.
  - `findings/_verified/` has no items awaiting submission past their stated review window.
  - `ops/ledger.md` is current (last entry within the last completed cycle).
  - Existing programs (`algolia`, `security`) have `last_synced` < 24h old (Task 1 must be deployed first).

**Blocked on:** agent-coordinator's BBP research list (DM sent at plan-start). When it arrives, pick the top candidate that passes all three filters:

1. **Public program on HackerOne** — API client is already wired for h1; another platform means new code, not this task.
2. **Low-density traffic** — `<50` active researchers, low recent report volume (proxy: bounty count per month). Coordinator's filter.
3. **Policy compatibility** — `rate-limited-OK` (full pipeline) or `manual-only` (runners refuse; operator scans by hand). `ambiguous` is **disallowed for this task** — the current `passive_recon` runner permits ambiguous + DNS but CLAUDE.md restricts ambiguous to Chaos/Shodan/archive only. That codebase-vs-spec drift must be resolved separately. If the only viable candidate is ambiguous, park this task.

**Files (per chosen slug `<X>`):**
- Create: `programs/hackerone/<X>/scope.md` — template from `programs/hackerone/algolia/scope.md`.
- Create: `programs/hackerone/<X>/roe.md` — template from `programs/hackerone/algolia/roe.md`. Default to the CLAUDE.md floor (no DoS, no social engineering, no destructive payloads, `pii_handling: synthetic_data_only`) unless the program's ToS authorizes more on a named environment.
- Optional: `programs/hackerone/<X>/notes.md` for operator-relevant context (selection rationale, program-specific quirks).

- [ ] **Step 1:** Receive coordinator's list. Pick one candidate per the three filters; record the rationale in the eventual commit message.
- [ ] **Step 2:** `mkdir -p programs/hackerone/<X>` and copy the two template files.
- [ ] **Step 3:** Edit `scope.md` — fill in `slug`, `title`, `platform_program_id`, leave `in_scope`/`out_of_scope` empty (scope-sync populates them), set `policy:` correctly.
- [ ] **Step 4:** Edit `roe.md` — fill in the program-specific authorities. Lean conservative; mirror algolia's floor when unsure.
- [ ] **Step 5 (optional):** If there's program-specific operator context worth preserving (selection rationale, ToS link, special notes), write it to `programs/hackerone/<X>/notes.md`. Skip if not applicable.
- [ ] **Step 6:** Policy-guard sanity check — **parser-only, no network**. From the laptop, after creating scope.md / roe.md:
  ```sh
  .venv/bin/python -c "
  import sys
  from earn_money import scope, config, policy
  s = scope.read_scope(config.Paths.from_root('.').scope_file('hackerone','<X>'))
  print('policy =', s.policy)
  if s.policy not in ('rate-limited-OK', 'manual-only'):
      sys.exit(f'ABORT: policy={s.policy!r} not allowed for this task')
  for mode in ('passive','active'):
      try:
          policy.require_policy_allows(s, mode=mode)
          print(f'  {mode}: ALLOWED')
      except policy.PolicyViolation:
          print(f'  {mode}: REFUSED')
  "
  ```
  Expected: `rate-limited-OK` → both ALLOWED; `manual-only` → both REFUSED. Any other policy (`ambiguous` or unknown) → script exits non-zero, task is parked.
- [ ] **Step 7:** Sync to VPS: `bash scripts/sync-vps.sh`.
- [ ] **Step 8:** Bootstrap scope on the VPS (so the H1 API call goes from the attributable egress IP with `RECON_ENABLED` in place):
  `ssh recon-vps 'cd /opt/earn-money && bin/scope-sync --platform hackerone --program <X>'` — expected `updated, hash=...`.
- [ ] **Step 9:** Wait one passive tick cycle (04:30 UTC) and confirm the program appears on `h1.cocode.dk`.
- [ ] **Step 10:** Commit: `git commit -m "feat(programs): onboard hackerone/<X> (low-density, policy: <tier>)"`. Note in the commit body why this program clears the Phase 5 gate.

## Notes

- Tasks 1 and 2 are independent and can land in either order.
- Task 3 depends on **both** Task 1 (Step 0's `last_synced < 24h` gate needs Task 1 deployed + one tick fired) and agent-coordinator's BBP research list. Either missing → park Task 3.
