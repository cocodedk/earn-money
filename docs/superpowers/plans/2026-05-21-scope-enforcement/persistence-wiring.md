# Persistence wiring

* `Scope` / `RoE` / `Program` are RUNTIME OBJECTS — never persisted to DB.
* The resolved `Program` (`platform`, `slug`, `scope`, `roe`) is attached to the scan-run runtime context and passed into every runner/fetcher. Celery payloads carry only serializable primitives (`platform`, `slug`, scope lists, RoE values); the worker reconstructs the dataclass. Do not re-resolve from a mutable target URL inside the fetcher.
* `OUT_OF_SCOPE_REJECTED` events go through the existing `Event.log()` pathway; visible in SSE stream + REST events endpoint immediately via 6D's panel. Payload must include `platform`, `program_slug`, `target_url`, `candidate_url`, `stub_id`, and rejection reason.
* `ScanRun.program_slug` could optionally be added as a CharField for triage filtering — but only if the Program model is referenced in the API. MVP: derive on scan-run start and keep it in runtime context, not as a DB relation.
