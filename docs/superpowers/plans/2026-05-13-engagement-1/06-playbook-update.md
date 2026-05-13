# Task 6 — Playbook update

**Files:**
- Modify: `ops/playbook.md`

Document the new operator surface. No tests — this is doc work, but the
pre-commit hook still runs `make smoke`, so do not let lint or type-check
break elsewhere in the same commit.

- [ ] **Step 1: Add a new section "Reading the queue"** above the existing
  "When the freeze flag fires" heading. Two short subsections:

  ```markdown
  ## Reading the queue

  ### Top of the queue: `bin/queue`

  ```bash
  bin/queue --program security
  ```

  Default shows the top 5 by severity DESC, then `first_seen` ASC. Pass
  `--all` to see the full backlog.

  ### One finding in detail: `bin/show`

  ```bash
  bin/show --program security <short-hash>
  ```

  Prints the queue (or `_resolved/info/`) markdown body, then the full
  audit history. Short hash is the 8-char prefix shown by `bin/queue`;
  show errors clearly on ambiguous or missing prefixes.
  ```

- [ ] **Step 2: Add a "Pre-active-recon preflight" section** above the
  "Triage rules of thumb" heading, mirroring the checklist in
  [`../../specs/2026-05-13-engagement-1/02-guardrails.md`](../../specs/2026-05-13-engagement-1/02-guardrails.md)
  exactly (policy still `rate-limited-OK`, `last_synced` within 24 h, no
  `FROZEN`, `RECON_ENABLED` present, egress IP matches the IP recorded in
  this same `playbook.md` file).

- [ ] **Step 3: Add a "Triage rules" note** under "Triage rules of thumb":

  > Suppression rules listed below are now enforced by the triage engine
  > and live in `triage_rules.yaml` at the repo root. Findings matching a
  > rule never reach `_queue/`; they land directly in `_resolved/info/`
  > with an audit row tagging the rule. To revisit a suppression, search
  > `findings_state_history.note` for `rule=<rule-name>`.

- [ ] **Step 4: `make smoke`** — must be green.

- [ ] **Step 5: Commit** as `docs(ops): playbook covers bin/queue, bin/show, preflight, suppression rules`.
