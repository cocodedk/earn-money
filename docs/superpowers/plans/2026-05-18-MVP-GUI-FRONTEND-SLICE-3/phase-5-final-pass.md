# Phase 5 — Final pass

Same checklist as slices 1 + 2:

- [ ] **Step 1: Full coverage** — `npm run test:coverage` → 100/100/100/100.
- [ ] **Step 2: Production build** — `npx vite build`; bundle size should grow ≤30 kB gzipped vs slice 2's 230/40 (Findings + Evidence + Target are mostly composition of existing primitives).
- [ ] **Step 3: Rebase onto `refactor/archive-v1`** — pull any peer Phase 2 work.
- [ ] **Step 4: Compose smoke**:
  1. Bring up stack from the worktree: `docker compose -p earn-money --env-file /home/cocodedk/0-projects/earn-money/.env up -d --build backend worker nginx frontend`.
  2. From the frontend: create project → set as current → add three lab targets → create scan run with stub 1.1 → start.
  3. While the run produces findings, navigate to `/findings`. Filter by `stub=1.1`. Each row appears as the runner emits it.
  4. Click into a finding → linked evidence row visible.
  5. Navigate to `/targets`, click a row's "Open results" → `/targets/<id>/results` shows the rollup.
- [ ] **Step 5: Tear down** backend/worker/nginx/frontend; leave postgres+redis healthy for peer.
- [ ] **Step 6: Merge back to `refactor/archive-v1`** — coordinate with peer before push.
