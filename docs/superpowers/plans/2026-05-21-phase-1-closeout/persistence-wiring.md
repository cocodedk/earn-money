# Persistence wiring

* Uses existing `Evidence` + `Finding` shapes from `apps/findings/models.py` (unchanged).
* `Finding.category`: `sql_orm_errors.<db_family>` for 1.19 / `well_known_paths.<family>` for WKP.
* `Finding.data` is family-specific JSON; frontend tolerates additive keys per [[project-merge-coordination]] rule (2) — _"in-stack PRs that don't touch the cross-tier contract need no pre-announce"_. No cross-tier announcement needed.
* `Finding.status` vocabulary: `candidate | confirmed | rejected | stale`. New evidence → `candidate`. Re-detection with matching dedup key → `confirmed`. Disappearance on subsequent scan with the same target → `stale`. Operator triage drives `rejected`.
* `Finding.severity`: `low | medium | high`, from per-family hint (env: high; git: high; logs: medium; config_files: medium; backup_archives: medium; db_dumps: high; sql_orm_errors: medium default, high if SQL fragment + table name both extractable).
* Dedup keys:
  * 1.19: `(target_id, signal_kind, fingerprint(error_excerpt_redacted))`.
  * WKP: `(target_id, family, candidate_path, signal_kind)`.
* `Event.log()` emits one row per state change in the same transaction per [[project-event-log-medium-done-well]]. **Event types needed**: `FINDING_CREATED` (NEW — must be added to `backend/apps/events/types.py` `EventType` enum; current enum has `FINDING_STATUS_CHANGED` but no creation event). Added in slice WKP-A step 5 (single owner; not duplicated in 19-B), with a test that asserts the enum value exists + round-trips through `Event.log()`. Existing `FINDING_STATUS_CHANGED` covers `candidate → confirmed → stale` transitions.
