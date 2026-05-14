# Agent layer — operator guide

The agent layer wraps every LLM call our pipeline makes. It enforces the [security boundaries](../superpowers/specs/2026-05-14-AGENT-design.md) the spec requires: untrusted-evidence wrapping, prompt-injection detection, per-action allowlist, structured-output retry, multi-provider routing, redacted audit log.

## Quickstart

1. Pick a provider. Set the env vars:

   ```bash
   # In /opt/earn-money/.env on the VPS
   EARN_MONEY_LLM_PROVIDER=openrouter        # or anthropic|openai|huggingface
   OPENROUTER_API_KEY=sk-or-...
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1     # optional, this is the default
   OPENROUTER_DEFAULT_MODEL=qwen/qwen3-235b-a22b
   OPENROUTER_SITE_URL=https://cocode.dk                 # optional
   OPENROUTER_APP_NAME=earn-money                        # optional
   OPENROUTER_TIMEOUT_SECONDS=60                         # optional
   ```

2. Install the provider extras: `pip install -e '.[agent-anthropic]'` / `'.[agent-openai]'` / `'.[agent-all]'`.

3. Run the agent-driven pipeline once: `bin/active-tick --intelligent --program algolia --max-targets 5`.

The dashboard's ACTIVE SCANS panel shows the chosen step in real time; proposals (if any) land under `scratch/agent-proposals/`; one JSONL row per LLM call is appended to `scratch/agent-audit/<date>.jsonl`.

## Task routing (spec §3 & §4)

Five built-in task profiles. Each maps to its own model env var; a global default catches anything unset.

| Task type               | Env var                                     | Suggested model           |
|-------------------------|---------------------------------------------|---------------------------|
| `default_assistant`     | `OPENROUTER_MODEL_DEFAULT_ASSISTANT`        | qwen/qwen3-235b-a22b      |
| `coding_security`       | `OPENROUTER_MODEL_CODING_SECURITY`          | qwen/qwen3-coder          |
| `report_writing`        | `OPENROUTER_MODEL_REPORT_WRITING`           | mistralai/mistral-small   |
| `structured_extraction` | `OPENROUTER_MODEL_STRUCTURED_EXTRACTION`    | ibm/granite               |
| `deep_reasoning`        | `OPENROUTER_MODEL_DEEP_REASONING`           | deepseek/deepseek-r1      |

Fallback: profile env → `OPENROUTER_DEFAULT_MODEL` → `RouterUnconfigured`. Unknown task strings collapse to `default_assistant`.

Verify model IDs are valid in OpenRouter's model list before deploying — vendor names change.

## Structured output (spec §5)

`from earn_money.agent.structured import request_structured`. Pass a JSON Schema; the helper sends `response_format` when the provider supports it, parses JSON on return, validates via your callback, and retries **once** with a repair prompt on failure. Beyond that → `StructuredOutputError`.

The scanner-analysis schema (`agent.schemas.SCANNER_ANALYSIS_SCHEMA`) is the canonical shape for finding analysis; pair it with `agent.schemas.parse_scanner_analysis` as the validator.

## Prompt-injection protection (spec §6-§9)

- **Trusted policy block** prepended to every system prompt — tells the model that anything in the user message is data, never instructions.
- **Evidence wrap** — recon content goes through `agent.evidence.wrap_evidence(...)` first. The result is an `<UNTRUSTED_SCANNED_EVIDENCE>` block with a sha256 hash, scan timestamp, source URL, invisible-char stripped, optionally truncated.
- **Injection detector** — ~20 patterns (ignore_previous, role_change, reveal_prompt, call_url, exfiltrate_to, mark_safe, suppress_finding, HTML/CSS/script-comment injection, base64 hidden payloads, …). Detector results land in the evidence metadata so the model is warned and `requires_human_review` flips on for downstream analysis.

## Action allowlist (spec §10)

`agent.action_allowlist` is the source of truth for what `proposed_actions[]` entries the agent may suggest. Low-risk (analysis, drafting) → allowed; medium (severity downgrade, propose new runner) → allowed but flips human review; high (active_exploitation, credential_use, shell_command, modify_scope, …) → hard-blocked regardless of what the model claims.

The model's own `risk_level` in the reply is **ignored** — the allowlist's policy is authoritative.

## Audit log (spec §13)

`scratch/agent-audit/<YYYY-MM-DD>.jsonl`. One row per decision. Every row passes through the redactor — Anthropic/OpenAI/HF/AWS/GitHub/Slack/Cookie-shaped strings are replaced with short markers before they hit disk.

Logged: event_type, platform/slug, timestamp, task, model_id (when known), prompt/schema versions, evidence_ids consulted, injection_indicators, proposed_actions (with validated outcomes), requires_human_review, finding_id.

Never logged: API keys, tokens, cookies, credentials, full sensitive payloads.

## Adding a new task profile

1. Add a value to `TaskType` in `agent/task_router.py`.
2. Add the env var name to `_PROFILE_ENV`.
3. Set the env var in the operator's `.env`.

No provider-layer change is needed — `Provider.complete(task=…)` forwards through.

## Adding another provider

1. Implement the `Provider` Protocol in `agent/providers.py` (or a sibling module if the SDK is heavy — see how OpenAI lives in `providers_openai_compat.py`).
2. Add an `elif name == "yourname":` branch in `from_env()`.
3. List the SDK as an extra in `pyproject.toml` under `[project.optional-dependencies]`.

## Running the tests

```
make smoke
# or just the agent suite:
.venv/bin/pytest tests/agent/ -q
```

## Files

- `src/earn_money/agent/policy_prompt.py` — trusted instruction block (§6).
- `src/earn_money/agent/evidence.py` — `wrap_evidence(...)` + invisible-char strip + truncation (§7, §9).
- `src/earn_money/agent/injection_detector.py` — deterministic pattern matcher (§8).
- `src/earn_money/agent/action_allowlist.py` — per-action-type policy (§10).
- `src/earn_money/agent/task_router.py` — task → model resolver (§3, §4).
- `src/earn_money/agent/providers.py` + `providers_openai_compat.py` — vendor adapters behind the `Provider` Protocol (§1, §2).
- `src/earn_money/agent/schemas.py` — scanner-analysis schema + validator (§11).
- `src/earn_money/agent/structured.py` — `request_structured(...)` with retry budget (§5).
- `src/earn_money/agent/decider.py` + `decider_helpers.py` — single-shot decider that ties it all together.
- `src/earn_money/agent/audit.py` — append-only audit log + redaction (§13).
- `src/earn_money/agent/proposals.py` — safe writer for agent-proposed scripts and tool-gap notes.
