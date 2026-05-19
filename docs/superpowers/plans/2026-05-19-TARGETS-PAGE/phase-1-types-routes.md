# Phase 1 — Types + routes registry

Add the `Target` and `CreateTargetBody` types alongside the existing `Project` types, and add `targetsNew` to the `ROUTES` registry. Foundation for everything downstream.

---

### Task A: Types + routes

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/app/routes.ts`

- [ ] **Step 1: Edit `frontend/src/types/api.ts`**

Append the following at the end of the file:

```ts
export type Target = {
  id: Uuid;
  project: Uuid;
  base_url: string;
  host: string;
  ip: string | null;
  status: TargetStatus;
  created_at: Iso8601;
  updated_at: Iso8601;
};

export type CreateTargetBody = {
  project: Uuid;
  base_url: string;
  host?: string;
  ip?: string | null;
};
```

Rationale: `host` is non-null on the Target row because the serializer derives it from `base_url` when blank (per backend commit `6b9802d`). `ip` is `string | null` because the serializer normalises blank → null. The Create body keeps `host` and `ip` optional so the operator can omit them.

- [ ] **Step 2: Edit `frontend/src/app/routes.ts`**

Replace the file contents with:

```ts
export const ROUTES = {
  index: "/",
  projects: "/projects",
  projectsNew: "/projects/new",
  targets: "/targets",
  targetsNew: "/targets/new",
  stubs: "/stubs",
  scanRuns: "/scan-runs",
  findings: "/findings",
  evidence: "/evidence",
  settings: "/settings",
} as const;
```

The only addition is the `targetsNew` line. Keep the existing `targets` entry untouched — it stays `/targets`.

- [ ] **Step 3: Verify typecheck still passes**

```bash
cd frontend && npm run typecheck
```

Expected: zero errors. There is no test added at this phase — types and route constants don't have meaningful runtime behaviour to assert. Phase 2 onward will exercise them.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/app/routes.ts
git commit -m "$(cat <<'EOF'
feat(frontend): add Target types + targetsNew route entry

Foundation for the Targets feature slice. Target.host is non-null because
the backend serializer derives it from base_url; Target.ip is nullable
because the serializer normalises blank to null. CreateTargetBody keeps
host and ip optional so the operator can omit them in the form.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Run `/simplify` and iterate**

After the commit lands:

```bash
/simplify
```

Iterate fix → commit → `/simplify` until all three review agents (reuse, quality, efficiency) return no actionable findings. This is a tiny commit so most likely converges in one pass.
