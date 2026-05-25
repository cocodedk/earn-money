        target = self._ensure_target(host)
        self.stdout.write(str(target.pk))

    def _wipe(self) -> dict[str, int]:
        from apps.agent.models import (
            AgentNote, AgentObservation, AgentAction, AgentTurn, AgentSession,
        )
        from apps.events.models import Event
        from apps.scans.models import ScanTargetRun, ScanRun

        tables = [
            ("AgentNote", AgentNote),
            ("AgentObservation", AgentObservation),
            ("AgentAction", AgentAction),
            ("AgentTurn", AgentTurn),
            ("AgentSession", AgentSession),
            ("Event", Event),
            ("ScanTargetRun", ScanTargetRun),
            ("ScanRun", ScanRun),
        ]
        counts = {}
        for name, model in tables:
            count, _ = model.objects.all().delete()
            counts[name] = count
        return counts

    def _ensure_target(self, host: str):
        from apps.projects.models import Project
        from apps.targets.models import ScanTarget

        target = ScanTarget.objects.filter(host=host).first()
        if target is not None:
            return target

        project, _ = Project.objects.get_or_create(
            name="lab", defaults={"name": "lab"},
        )
        return ScanTarget.objects.create(
            host=host,
            base_url=f"https://{host}",
            project=project,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/test.sh backend apps/agent/tests/test_reset_lab_db.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/agent/management/ backend/apps/agent/tests/test_reset_lab_db.py
git commit -m "feat(agent): add reset_lab_db management command"
```

---

### Task 2: Wire CLEAN_SLATE into run-mission.sh

**Files:**
- Modify: `scripts/run-mission.sh`

- [ ] **Step 1: Add CLEAN_SLATE block after env var setup**

After the `DRY_RUN` variable (line 33), add:

```sh
CLEAN_SLATE="${CLEAN_SLATE:-0}"
CLEAN_SLATE_CONFIRM="${CLEAN_SLATE_CONFIRM:-}"
VPS_HOST="${VPS_HOST:-recon-vps}"
VPS_PATH="${VPS_PATH:-/opt/earn-money/}"
```

After the TIMEOUT validation (line 40), add the clean-slate block:

```sh
# --- Clean slate (optional) ---
if [ "$CLEAN_SLATE" = "1" ]; then
  [ "$CLEAN_SLATE_CONFIRM" = "DELETE_LAB_DB" ] || \
    die "CLEAN_SLATE=1 requires CLEAN_SLATE_CONFIRM=DELETE_LAB_DB"

  log "CLEAN SLATE: wiping agent/scan/event data on ${VPS_HOST}"
  RESET_OUTPUT=$(ssh "${VPS_HOST}" "cd '${VPS_PATH}' && \
    docker compose exec -T backend python manage.py reset_lab_db \
      --host '${TARGET_ARG}' --confirm DELETE_LAB_DB" 2>&1) \
    || die "Clean slate failed: ${RESET_OUTPUT}"

  # Parse target UUID from command output (last non-empty line of stdout)
  TARGET_ID=$(echo "$RESET_OUTPUT" | grep -E '^[0-9a-f-]{36}$' | tail -1)
  [ -n "$TARGET_ID" ] && log "target seeded: $TARGET_ID"

  # Log deletion stats (stderr lines from the command)
  echo "$RESET_OUTPUT" | grep "deleted" | while read -r line; do
    log "$line"
  done
fi
```

Then modify the target resolution block to skip lookup when TARGET_ID is already set:

```sh
# --- Resolve target (UUID or host lookup) ---
if [ -n "${TARGET_ID:-}" ]; then
  log "target ID (from clean slate): $TARGET_ID"
elif ...
```

- [ ] **Step 2: Test manually with DRY_RUN**

```bash
CLEAN_SLATE=1 CLEAN_SLATE_CONFIRM=DELETE_LAB_DB DRY_RUN=1 \
  API_BASE=https://h1.cocode.dk ./scripts/run-mission.sh juiceshop.cocode.dk
```

- [ ] **Step 3: Commit**

```bash
git add scripts/run-mission.sh
git commit -m "feat(scripts): add CLEAN_SLATE option to run-mission.sh"
```
