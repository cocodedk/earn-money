# Phase 8 — Final pass

Acceptance for slice 2 before merging back to `refactor/archive-v1`.

---

- [ ] **Step 1: Full coverage**

```bash
cd /home/cocodedk/0-projects/earn-money-frontend-slice-2/frontend
npm run test:coverage
```

Expected: 100/100/100/100 on `src/**/*.{ts,tsx}` (minus the documented exclusions).

- [ ] **Step 2: Production build**

```bash
npx vite build
```

Expected: build succeeds, no TypeScript errors. Bundle size should not have grown more than ~50kB gzipped vs slice 1 (~67kB). If it has, identify the culprit (likely an inadvertent dep import — `markdown-it`, etc.).

- [ ] **Step 3: Rebase onto latest `refactor/archive-v1`**

Peer may have landed stubs 1.2 through 1.7 while slice 2 was being implemented. Rebase to pull their backend in.

```bash
git fetch origin
git rebase refactor/archive-v1
```

If rebase finds conflicts in shared files (unlikely — frontend lives separately from backend), resolve carefully or stash slice-2 changes and re-cherry-pick.

- [ ] **Step 4: Compose smoke against real backend**

```bash
cd /home/cocodedk/0-projects/earn-money-frontend-slice-2  # repo root in worktree
docker compose build backend frontend
docker compose up -d backend worker nginx frontend
sleep 8
docker compose ps
curl -sS http://localhost/api/health/
```

Then open `http://localhost/` and walk the operator path:
1. Create project → success
2. Set as current → chip updates
3. Add three targets (`dvwa.cocode.dk`, `webgoat.cocode.dk`, `juiceshop.cocode.dk`) → 3 rows
4. Open `/stubs` → see `1.1`, `1.2` (and any others peer has landed)
5. Click into `1.1` → body renders
6. Create scan run with stub `1.1` and all three targets → land on detail
7. Click Start → status flips to running → live events stream in
8. After a few seconds, click Stop → status flips through `stopping` → `stopped`
9. Verify findings appear (from peer's 1.1 framework-detection runner)

Document any UX rough edges as slice-3 follow-ups.

- [ ] **Step 5: Tear down**

```bash
docker compose stop backend worker nginx frontend
# Postgres + redis stay up for peer
```

Notify peer the stack is back to their quiet state.

- [ ] **Step 6: Merge back to `refactor/archive-v1`**

Coordinate with peer first. Likely path:

```bash
cd /home/cocodedk/0-projects/earn-money  # main checkout
git checkout refactor/archive-v1
git pull
git merge --no-ff feat/em-frontend-slice-2
```

`--no-ff` keeps the slice-2 branch history intact as a discoverable unit. Push only after operator authorisation.

- [ ] **Step 7: Cleanup**

After merge, the worktree branch is no longer needed for new work. Either:

- **Remove the worktree** if slice 3 will get its own:
  ```bash
  git worktree remove /home/cocodedk/0-projects/earn-money-frontend-slice-2
  git branch -d feat/em-frontend-slice-2
  ```
- **Keep it around** if you want to retain the slice-2 history close at hand. Either is fine.
