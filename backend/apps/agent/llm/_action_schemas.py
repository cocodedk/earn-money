"""Action schema snippets for the LLM system prompt."""

ACTION_SCHEMA_SNIPPETS: dict[str, str] = {
    "observe_page": (
        '### observe_page\n'
        '{ "action": "observe_page", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "include_screenshot": false, "element_ids": null }'
    ),
    "navigate": (
        '### navigate\n'
        '{ "action": "navigate", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "path": "/some/path" }'
    ),
    "inspect_asset": (
        '### inspect_asset\n'
        '{ "action": "inspect_asset", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "asset_ref": "asset-id" }'
    ),
    "click": (
        '### click\n'
        '{ "action": "click", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "element_id": "link_3" }'
    ),
    "http_request": (
        '### http_request\n'
        '{ "action": "http_request", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "method": "GET", "path": "/api/endpoint" }\n'
        '   method must be GET or HEAD. Same-origin only. No request body.'
    ),
    "store_note": (
        '### store_note\n'
        '{ "action": "store_note", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "note_type": "hypothesis|gap|route|parameter|candidate|credential_label|form",\n'
        '   "content": {} }'
    ),
    "submit_candidate": (
        '### submit_candidate\n'
        '{ "action": "submit_candidate", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "category": "...", "description": "...", "evidence_refs": [] }'
    ),
    "request_phase_transition": (
        '### request_phase_transition\n'
        '{ "action": "request_phase_transition", "goal": "...", "reason": "...",\n'
        '   "hypothesis": "...", "from_phase": "...", "to_phase": "...",\n'
        '   "evidence_refs": [], "remaining_questions": null }'
    ),
    "fill_form": (
        '### fill_form\n'
        '{ "action": "fill_form", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "element_id": "input_1", "value": "test" }'
    ),
    "submit_form": (
        '### submit_form\n'
        '{ "action": "submit_form", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "element_id": "btn_0" }'
    ),
    "run_stub": (
        '### run_stub\n'
        '{ "action": "run_stub", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "stub_id": "stub-name", "params": {} }'
    ),
    "run_tool": (
        '### run_tool\n'
        '{ "action": "run_tool", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "tool_id": "tool-name", "params": {} }'
    ),
    "request_verify": (
        '### request_verify\n'
        '{ "action": "request_verify", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "finding_ref": "candidate-id", "rationale": "..." }'
    ),
    "diff_response": (
        '### diff_response\n'
        '{ "action": "diff_response", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "baseline_ref": "asset-id", "current_ref": "asset-id" }'
    ),
    "compare_baseline": (
        '### compare_baseline\n'
        '{ "action": "compare_baseline", "goal": "...", "reason": "...", "hypothesis": "...",\n'
        '   "baseline_ref": "asset-id", "target_ref": "asset-id" }'
    ),
    "stop": (
        '### stop\n'
        '{ "action": "stop", "goal": "...", "reason": "...", "hypothesis": "..." }'
    ),
}

DISPLAY_ORDER = [
    "observe_page", "navigate", "inspect_asset", "click",
    "fill_form", "submit_form", "http_request",
    "run_stub", "run_tool", "request_verify",
    "diff_response", "compare_baseline",
    "store_note", "submit_candidate", "request_phase_transition", "stop",
]
