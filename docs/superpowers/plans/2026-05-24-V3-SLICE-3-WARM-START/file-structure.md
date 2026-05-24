# File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/apps/agent/target_intel.py` | Create | `TargetIntel`, `FormSignature`, `PriorCandidate` dataclasses + deterministic `build_target_intel(exclude_session_id=...)` + sanitized `format_intel_prompt()` |
| `backend/apps/agent/plateau.py` | Modify | Accept optional `known_routes` baseline in constructor |
| `backend/apps/agent/llm/prompts.py` | Modify | Accept optional `prior_intel_section` param in `build_system_prompt()` |
| `backend/apps/agent/controller.py` | Modify | Accept optional `target_intel` param, pass to prompt and plateau |
| `backend/apps/agent/tasks.py` | Modify | Query prior session, build intel, pass to controller |
| `backend/apps/agent/controller_dispatch.py` | Modify | Pass route_paths to plateau `record_turn()` |
| `backend/apps/agent/tests/test_target_intel.py` | Create | Tests for `build_target_intel()` and `format_intel_prompt()` |
| `backend/apps/agent/tests/test_plateau.py` | Modify | Tests for baseline route filtering |
| `backend/apps/agent/tests/test_prompts.py` | Modify | Tests for prior intel section in prompt |
| `backend/apps/agent/tests/test_controller.py` | Modify | Tests for warm-start wiring through controller |
| `backend/apps/agent/tests/test_tasks.py` | Modify | Test that `target_intel` is passed to MissionController |
| `backend/apps/agent/tests/test_controller_dispatch.py` | Create/Modify | Test browser dispatch passes discovered route paths to plateau |
