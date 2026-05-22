# Task 6 — spec-review + code-review + PR

**Goal:** Audit the implementation against the spec, run hygiene reviews, open the PR.

## Steps

- [ ] **Step 1: Spec-review audit**

Read `docs/superpowers/specs/2026-05-22-auth-events-panel-design.md` end-to-end and check the implementation against the acceptance criteria. Confirm:

- All 3 canonical event-type strings appear in `AUTH_EVENT_TYPES` and are sent as `?type=` params.
- The 3 severity → `data-variant` mappings (`warning` / `info` / `alert`) are exercised by tests.
- Empty-state (count=0) is asserted at the panel level.
- "+N more" hint is asserted both shown and hidden.
- Newest-first ordering is asserted at both the hook and the panel level.
- Accessibility: `aria-expanded` + keyboard activation (Enter + Space) are asserted.
- Error tolerance: a failed auth-events request does not block or crash the target result page.
- Page placement: integration test confirms `target-evidence-section` < `target-auth-events-section` < `target-events-section`.

If any acceptance criterion lacks a test, add one and commit it.

- [ ] **Step 2: Run `/code-review high`**

Per `CLAUDE.md` commit hygiene: after the implementation commits, run `/code-review high` over the branch. Fix findings as small follow-up commits. Loop until clean. If the worker environment does not expose `/code-review`, run the repository's highest available review workflow and document the substitute in the PR body.

- [ ] **Step 3: Capture rollback plan**

Confirm the PR description includes this rollback note:

```md
## Rollback

This is frontend-only and split into task-sized commits. To hide the feature after merge, revert the Task 5 e2e commit and Task 4 mount commit first. To remove the implementation entirely, revert all auth-events-panel commits in reverse order. No data migration or backend rollback is required.
```

- [ ] **Step 4: Push branch**

```bash
git push origin feat/em-frontend-auth-events-panel
```

- [ ] **Step 5: Open PR**

```bash
gh pr create --base main --head feat/em-frontend-auth-events-panel \
  --title "feat(frontend): auth events panel on target result page" \
  --body "$(cat <<'EOF'
## Summary

Phase 2 surfaces three new auth event types on the target result page as colour-coded expand-in-place pills:

- `auth.probe_refused` → amber (warning) — RoE / policy refusal
- `auth.fixture_required` → blue (info) — needs operator config
- `auth.finding_candidate` → red (alert) — possible vuln pending verify

Dedicated `useTargetAuthEventsQuery(targetId)` issues a single paginated request with multi-value `?type=` and reverses the backend's oldest-first results client-side. The panel slot lands between `TargetEvidencePanel` and `TargetEventsTable`; it omits itself when the target has no auth events.

Spec: `docs/superpowers/specs/2026-05-22-auth-events-panel-design.md`
Plan: `docs/superpowers/plans/2026-05-22-auth-events-panel/`

## Test plan
- [ ] `cd frontend && npm run test` — full suite green
- [ ] `cd frontend && npx tsc -b` — no errors
- [ ] `cd frontend && npm run test:coverage` — 100% on the new files
- [ ] Visual: a target with at least one `auth.fixture_required` event renders the panel above the full events feed, pill expands to show message + JSON payload

## Rollback

This is frontend-only and split into task-sized commits. To hide the feature after merge, revert the Task 5 e2e commit and Task 4 mount commit first. To remove the implementation entirely, revert all auth-events-panel commits in reverse order. No data migration or backend rollback is required.
EOF
)"
```

- [ ] **Step 6: Ping em-backend on the bus with the PR URL**

Use `mcp__claude-chat__chat_message_agent` with `_caller="agent-em-frontend"` and `to_agent="agent-em-backend"` to notify of the open PR. Include the PR URL and the SHA of the tip. If the bus tool is unavailable, add a short `Backend coordination` note to the PR body and call out the missing notification in the implementation handoff; do not block the PR solely on this notification.
