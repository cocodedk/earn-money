# OSS Tool Mapping — Phase 24: AI/LLM-Specific Webapp Vectors

> Maps each stub to proven OSS tools. Our platform wraps these for orchestration,
> result normalization, and persistence. Do not re-implement detection logic already
> covered by a mature OSS tool.
>
> Note: AI/LLM security tooling is rapidly evolving. Many stubs in this phase require
> custom probe logic on top of general-purpose tools — the OSS tools below provide
> the transport and injection layer; detection logic is platform-specific.

## Crawler Layer (critical — required by all stubs)

| Tool | Repo | Why |
|------|------|-----|
| Katana | https://github.com/projectdiscovery/katana | Fast JS-aware endpoint discovery |
| ZAP Spider | https://github.com/zaproxy/zaproxy | Passive+active crawl integrated with scanning |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Scriptable proxy for auth-gated crawling |
| Playwright | https://github.com/microsoft/playwright | JS-heavy SPA crawling with real browser |
| hakrawler | https://github.com/hakluke/hakrawler | Fast passive crawl from JS/HTML links |

## Stub Mappings

### 24.01 — Prompt Injection

**Detects:** Direct prompt injection via user-controlled input fields that influence LLM system prompt behaviour.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| garak | https://github.com/NVIDIA/garak | Primary: purpose-built LLM red-team; prompt injection probe suite |
| promptfoo | https://github.com/promptfoo/promptfoo | Adversarial prompt evaluation with configurable attack strategies |
| PyRIT | https://github.com/Azure/PyRIT | Red-team orchestration; multi-turn injection and jailbreak probes |
| Ffuf | https://github.com/ffuf/ffuf | Transport layer: fuzz text/chat endpoints with injection wordlists |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Transport layer: intercept and inject payloads into request fields |

### 24.02 — Indirect Prompt Injection Through Webpages/Files

**Detects:** LLM retrieves external content (pages, files, emails) containing injected instructions.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| garak | https://github.com/NVIDIA/garak | Indirect injection probes: retrieval-augmented attack strategies |
| PyRIT | https://github.com/Azure/PyRIT | Multi-turn indirect injection; document poisoning scenarios |
| promptfoo | https://github.com/promptfoo/promptfoo | Adversarial prompt evaluation for indirect injection via retrieved content |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept outbound retrieval requests; serve crafted poisoned content |
| Playwright | https://github.com/microsoft/playwright | Render attacker-controlled pages the LLM agent visits |
| Ffuf | https://github.com/ffuf/ffuf | Transport layer: fuzz URL/file parameters passed to context-loading |

### 24.03 — Tool Call Manipulation

**Detects:** LLM agent tool calls that can be hijacked via injected instructions to invoke unintended tools.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| garak | https://github.com/NVIDIA/garak | Tool-use injection probe suite; tests function-call hijacking |
| PyRIT | https://github.com/Azure/PyRIT | Agentic orchestration: injects adversarial instructions to trigger tool-selector and argument-level manipulation |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Transport: intercept tool-call API requests; inspect/modify tool-name and argument fields |
| Ffuf | https://github.com/ffuf/ffuf | Transport: fuzz tool-name and argument fields in agent API requests |

### 24.04 — Data Exfiltration Through Model Output

**Detects:** LLM responses that leak sensitive data from other users, system context, or backend stores.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| garak | https://github.com/NVIDIA/garak | Data-exfil and leak-replay probe categories; purpose-built for LLM |
| truffleHog | https://github.com/trufflesecurity/trufflehog | Scans LLM output content for secrets and credentials |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Capture all LLM responses for offline secret/PII pattern analysis |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates matching sensitive data patterns in model responses |

### 24.05 — Retrieval Poisoning

**Detects:** RAG/vector-store contents that can be poisoned with attacker-controlled documents to influence retrieval.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| PyRIT | https://github.com/Azure/PyRIT | Document poisoning scenarios; RAG/vector-store adversarial content |
| garak | https://github.com/NVIDIA/garak | RAG and retrieval probes; adversarial document injection |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept document upload to inject adversarial content |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz document ingestion endpoints with poisoned content |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for exposed document/embedding ingestion APIs |

### 24.06 — Cross-User Memory Leakage

**Detects:** LLM memory/session stores that expose one user's context to another.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with multi-user session switching to probe memory isolation |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept memory-read requests with swapped session tokens |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz memory/session ID parameters to enumerate other users' data |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for IDOR on LLM memory/history endpoints |

### 24.07 — Unsafe Agent Actions

**Detects:** LLM agents that execute destructive/irreversible actions (delete, send, pay) without confirmation gates.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| garak | https://github.com/NVIDIA/garak | Agentic-safety probes: tool-invocation attack suite for destructive action bypass |
| PyRIT | https://github.com/Azure/PyRIT | Multi-turn agent coercion: crafts prompts that bypass confirmation gates |
| Playwright | https://github.com/microsoft/playwright | Drive UI flows that trigger agent actions; test for confirmation dialogs |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Transport: intercept agent action requests; remove confirmation tokens |
| Ffuf | https://github.com/ffuf/ffuf | Transport: fuzz agent action triggers for missing authorization checks |

### 24.08 — Insecure Plugin/Tool Permissions

**Detects:** LLM plugins granted excessive permissions (filesystem, network, code execution) beyond task scope.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan probes plugin API endpoints for scope enforcement |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for over-permissioned plugin registration endpoints |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Inspect plugin manifest requests and permission grant flows |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz plugin permission scope parameters during registration |

### 24.09 — Model Output Trusted as Policy Decision

**Detects:** Application logic that passes LLM output directly into access-control or policy evaluation without validation.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| garak | https://github.com/NVIDIA/garak | Policy-bypass and output-manipulation probes; adversarial model inputs |
| promptfoo | https://github.com/promptfoo/promptfoo | Adversarial eval: measures whether prompt variants flip policy verdicts |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Transport: intercept LLM response pipeline; inject false policy verdicts |
| Ffuf | https://github.com/ffuf/ffuf | Transport: fuzz policy-decision endpoints with crafted LLM-output lookalikes |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates targeting endpoints that parse/evaluate model output as truth |
