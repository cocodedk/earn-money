### File 9: `.env.example` (UPDATED — pentesting model configuration)

```env
# OpenRouter configuration
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://your-pentest-tool.local
OPENROUTER_APP_NAME=PentestProbe

# Default model (fallback for all tasks)
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-r1

# Task-specific models — PENTESTING OPTIMIZED
# Primary attack loop: uses deep reasoning for exploit chain analysis
OPENROUTER_MODEL_PENTEST_LOOP=deepseek/deepseek-r1

# Planning: strong instruction follower
OPENROUTER_MODEL_AGENT_PLANNING=qwen/qwen3-235b-a22b

# Deep reasoning: chain-of-thought for initial recon
OPENROUTER_MODEL_DEEP_REASONING=deepseek/deepseek-r1

# Code analysis: specialized for JS/HTML/response analysis
OPENROUTER_MODEL_CODE_ANALYSIS=qwen/qwen3-coder

# Structured extraction: JSON output from observations
OPENROUTER_MODEL_STRUCTURED_EXTRACTION=qwen/qwen3-235b-a22b

# Report writing: good prose for findings
OPENROUTER_MODEL_REPORT_WRITING=mistralai/mistral-small

# General assistant (not used for pentesting)
OPENROUTER_MODEL_DEFAULT_ASSISTANT=mistralai/mistral-small

# Dashboard settings
RECON_ENABLED=true
PROBE_MAX_TURNS=10
PROBE_MAX_REQUESTS=30

# Budget
LLM_MAX_CALLS_PER_SCAN=50
LLM_MAX_TOKENS_PER_REQUEST=16000
LLM_DEFAULT_MAX_OUTPUT_TOKENS=4000
```

