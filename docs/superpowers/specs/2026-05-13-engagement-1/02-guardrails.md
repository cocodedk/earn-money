# 02 — Guardrails

Three guardrails sit on top of the existing triage engine. None of them
modifies the runners.

## Queue cap (cursor critique #3)

The design spec mandates "a hard cap on queue items presented per day" as the
top mitigation for triage overload. This engagement enforces the cap at the
**view layer**, not at the engine:

- Engine still writes every survived finding into `_queue/` and the DB.
- `bin/queue` lists at most **5** items by default, highest-severity first,
  then oldest-`first_seen` first. A `--all` flag shows the full queue.
- The cap is a presentation default. The triage backlog beyond 5 is visible
  on demand, not hidden.

5 is the working budget. If the operator regularly hits the `--all` flag and
finds value past item 5, raise it; if items 1–5 are mostly noise, lower it.

## Suppression audit trail (cursor critique #4)

The triage engine encodes the playbook's "rules of thumb" as auto-resolve
rules — known-noise nuclei templates that bypass `_queue/` and land directly
in `_resolved/info/`. Each auto-suppression records:

- The rule name that fired (e.g., `noise.csp-script-src-wildcard`).
- The matched nuclei template ID and template version (from the scan output).
- The timestamp of the suppression.
- A short `reason` string (one of: `playbook-noise`, `info-no-impact`, …).

The audit goes into the existing `findings_state_history` table — one row
per suppression with `to_state = 'resolved_info'`, `actor = 'triage-engine'`,
and a structured `note` of the form `rule=<rule> template=<id> version=<ver>
reason=<short>`. No schema migration, grep-able from SQLite for the monthly
retro spot-check.

## Preflight (one-shot checklist, no new CLI)

Before any active recon traffic in this engagement, the operator confirms
manually:

- [ ] Policy for `hackerone/security` is still `rate-limited-OK` in `scope.md`.
- [ ] `last_synced` is within the last 24 h.
- [ ] No `FROZEN` file in `programs/hackerone/security/`.
- [ ] `RECON_ENABLED` exists in the VPS repo root.
- [ ] Egress IP on the VPS still matches the recorded value
      (`178.105.140.53`).

A failed check halts the engagement. No script wraps this — it's five
seconds of operator attention before pulling the trigger.
