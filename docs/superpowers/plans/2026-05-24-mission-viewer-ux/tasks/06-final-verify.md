---
tier: FAST
depends_on: [01-intent-lines, 02-outcome-digest, 03-observation-details, 04-discovery-chips, 05-budget-bars]
files:
  modifies: []
allow_extra_files: false
---

# Task 6: Final Verification

**Goal:** Run full test suite and type check to confirm everything works together.

- [ ] **Step 1: Run full test suite**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 2: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Check line counts**

Run: `wc -l frontend/src/features/missions/*.tsx frontend/src/features/missions/*.ts frontend/src/features/missions/*.css`
Expected: All files under 200 lines.

- [ ] **Step 4: Push and create PR**

```bash
git push -u origin feat/em-frontend-mission-viewer-ux
gh pr create --title "feat(frontend): mission viewer UX — intent, outcomes, chips, structured details, budget bars" --body "5 UX improvements wired into the mission viewer page."
```
