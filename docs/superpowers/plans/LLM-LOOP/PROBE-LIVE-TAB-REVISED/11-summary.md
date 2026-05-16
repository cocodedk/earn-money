## Summary: Why This Fixes Everything

1. **Model selection fixed**: `coerce_task()` now properly maps `"agent_planning"` → `TaskType.AGENT_PLANNING`

2. **Pentesting-optimized models**: DeepSeek R1 for reasoning, Qwen Coder for code analysis, proper defaults for pentesting tasks

3. **Intelligent per-turn model selection**: Different models for recon vs. analysis vs. extraction phases

4. **Pentesting safety prompt**: The system prompt now establishes authorized testing context so models don't refuse to analyze vulnerabilities

5. **Live monitoring**: Full SSE streaming showing model selection, turn-by-turn actions, policy decisions, observations, and findings

6. **Complete frontend**: Tab-based UI with real-time turn cards, finding badges, token usage, and error handling

The probe tab now shows exactly what's happening each turn — which model was selected, why, what action was proposed, whether policy allowed it, what came back from the target, and what findings were discovered.
