# Out of Scope (Deferred)

These items are explicitly deferred from slice 1. See
[spec 10-slice-1.md](../../specs/2026-05-23-V3-AGENT-ARCHITECTURE/10-slice-1.md)
for the full list.

- AgentCheckpoint model and operator gates
- AgentPhaseTransition table
- probe/verify phases
- v2 stub integration (`run_stub` action)
- OSS tool integration (`run_tool` action)
- `click`, `fill_form`, `submit_form`, `http_request`, `request_verify` actions
- Finding promotion from candidates
- Multi-provider routing, cheap/frontier escalation
- Delta observations (full observations only)
- RoE amendment records
- Celery task integration
- `observations/redaction.py` (inline in builder for slice 1)
- `llm/router.py` (single model, no routing)
