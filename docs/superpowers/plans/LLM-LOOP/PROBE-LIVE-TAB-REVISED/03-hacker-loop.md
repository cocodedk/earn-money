### File 3: `pentest_tools/hacker_loop.py` (FIXED — model selection per turn)

```python
"""HackerLoop — fixed with intelligent model selection per turn phase."""

import json
import logging
from typing import Optional
from dataclasses import dataclass, field

from .llm.task_router import TaskType, resolve_model, coerce_task
from .llm.providers import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class TurnEvent:
    """Emitted for live monitoring — one per loop iteration."""
    turn: int
    task_type: str
    model: str
    prompt_summary: str
    raw_action: str
    parsed_action: Optional[dict]
    policy_decision: dict
    observation: Optional[dict]
    candidates: list
    verified: list
    token_usage: dict


class HackerLoop:
    """Main pentesting loop with per-turn model selection."""
    
    def __init__(
        self,
        llm: LLMProvider,
        target_url: str,
        roe_profile: dict,
        max_turns: int = 10,
        event_callback: Optional[callable] = None,  # For live monitoring
    ):
        self.llm = llm
        self.target_url = target_url
        self.roe = roe_profile
        self.max_turns = max_turns
        self.event_callback = event_callback
        
        self.turn = 0
        self.session_state = {
            "urls": [target_url],
            "observations": [],
            "findings": [],
            "denials": 0,
        }
    
    def run(self):
        """Execute the pentesting loop."""
        while self.turn < self.max_turns:
            self.turn += 1
            
            # SELECT MODEL BASED ON TURN PHASE
            task_type = self._select_task_type()
            model = resolve_model(task_type)
            
            # Build prompt
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt()
            
            # Get LLM response
            raw_response = self.llm.complete(
                system=system_prompt,
                user=user_prompt,
                task=task_type.name.lower(),
                response_format=self._action_schema(),
            )
            
            # Parse action
            action = self._parse_action(raw_response)
            
            # Policy check
            policy_decision = self._check_policy(action)
            
            # Execute if allowed
            observation = None
            if policy_decision["allowed"]:
                observation = self._execute_action(action)
                self._process_observation(observation)
            else:
                self.session_state["denials"] += 1
                if self.session_state["denials"] >= 3:
                    self._emit_event("done", {"stop_reason": "repeated_denials"})
                    break
            
            # Emit turn event for live monitoring
            event = TurnEvent(
                turn=self.turn,
                task_type=task_type.name,
                model=model,
                prompt_summary=user_prompt[:200],
                raw_action=raw_response,
                parsed_action=action,
                policy_decision=policy_decision,
                observation=observation,
                candidates=self.session_state.get("pending_candidates", []),
                verified=self.session_state.get("findings", []),
                token_usage=self._estimate_tokens(raw_response),
            )
            self._emit_event("turn", event.__dict__)
            
            # Check stop conditions
            if action.get("tool") == "stop":
                self._emit_event("done", {"stop_reason": action.get("args", {}).get("reason", "llm_stop")})
                break
        
        # Max turns reached
        if self.turn >= self.max_turns:
            self._emit_event("done", {"stop_reason": "max_turns"})
    
    def _select_task_type(self) -> TaskType:
        """Intelligently select task type based on loop phase.
        
        THIS IS THE KEY FIX: Different turns need different models.
        """
        # Turn 1-2: Initial reconnaissance — use reasoning model
        if self.turn <= 2:
            return TaskType.DEEP_REASONING
        
        # When we have response data to analyze — use code analysis
        if self.session_state["observations"]:
            last_obs = self.session_state["observations"][-1]
            if self._has_complex_response(last_obs):
                return TaskType.CODE_ANALYSIS
        
        # When we have findings to extract — use structured extraction
        if self.session_state.get("pending_candidates"):
            return TaskType.STRUCTURED_EXTRACTION
        
        # Normal attack planning — use the pentesting loop model
        return TaskType.PENTEST_LOOP
    
    def _has_complex_response(self, observation: dict) -> bool:
        """Check if response needs deep analysis (JS, large HTML, API responses)."""
        body = observation.get("body", "")
        content_type = observation.get("headers", {}).get("content-type", "")
        
        return (
            "javascript" in content_type
            or "json" in content_type
            or len(body) > 500
            or "<script" in body.lower()
        )
    
    def _emit_event(self, event_type: str, data: dict):
        """Send event to live monitoring callback."""
        if self.event_callback:
            self.event_callback(event_type, data)
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for pentesting context."""
        return f"""You are conducting an authorized penetration test against {self.target_url}.

Available actions: get, post, set_header, store, report_candidate, stop.

Rules of Engagement:
- Allowed hosts: {', '.join(self.roe.get('allowed_hosts', [self.target_url]))}
- GET allowed: {self.roe.get('allow_get', True)}
- POST allowed: {self.roe.get('allow_post', True)}
- IDOR checks: {self.roe.get('allow_idor_checks', True)}
- Bruteforce: {self.roe.get('allow_bruteforce', False)}

Return exactly one JSON action per response. No explanations, no markdown."""
    
    def _build_user_prompt(self) -> str:
        """Build user prompt with session state."""
        observations_text = "\n".join(
            f"[Obs {i}] {obs['method']} {obs['url']} → {obs['status']} "
            f"(body: {obs.get('body', '')[:200]})"
            for i, obs in enumerate(self.session_state["observations"][-5:])
        )
        
        return f"""Session state:
- Turn: {self.turn}/{self.max_turns}
- URLs discovered: {self.session_state['urls']}
- Observations:
{observations_text}

What action should I take next?"""
    
    def _action_schema(self) -> dict:
        """JSON schema for pentesting actions."""
        return {
            "type": "object",
            "properties": {
                "tool": {
                    "type": "string",
                    "enum": ["get", "post", "set_header", "store", "report_candidate", "stop"]
                },
                "category": {"type": "string"},
                "args": {"type": "object"},
                "reasoning": {"type": "string"},
                "injection_detected": {"type": "boolean"},
            },
            "required": ["tool", "args"]
        }
    
    def _parse_action(self, raw: str) -> dict:
        """Parse LLM response into action dict. Fails closed."""
        try:
            # Extract JSON from response (handle markdown wrapping)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 2)[-1].rsplit("```", 1)[0]
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse action: {e}")
            return {"tool": "stop", "args": {"reason": "invalid_json"}}
    
    def _check_policy(self, action: dict) -> dict:
        """Check action against RoE policy."""
        tool = action.get("tool", "")
        category = action.get("category", "")
        
        # Allowlist check
        allowed_actions = ["get", "post", "set_header", "store", "report_candidate", "stop"]
        if tool not in allowed_actions:
            return {"allowed": False, "reason": f"Unknown tool: {tool}"}
        
        # POST restriction
        if tool == "post" and not self.roe.get("allow_post", False):
            return {"allowed": False, "reason": "POST not allowed in RoE"}
        
        # Bruteforce restriction
        if category == "bruteforce" and not self.roe.get("allow_bruteforce", False):
            return {"allowed": False, "reason": "Bruteforce not allowed in RoE"}
        
        return {"allowed": True, "reason": f"{tool.upper()} allowed"}
    
    def _execute_action(self, action: dict) -> dict:
        """Execute the action against the target. Returns observation."""
        # ... HTTP request execution ...
        pass
    
    def _process_observation(self, observation: dict):
        """Process observation for findings."""
        self.session_state["observations"].append(observation)
        # ... finding verification logic ...
    
    def _estimate_tokens(self, response: str) -> dict:
        """Rough token estimate."""
        return {
            "response_chars": len(response),
            "estimated_tokens": len(response) // 4,  # Rough estimate
        }
```

