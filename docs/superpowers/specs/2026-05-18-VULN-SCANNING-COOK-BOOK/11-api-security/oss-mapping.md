# OSS Tool Mapping — Phase 11: API Security

> Maps each stub to proven OSS tools. Our platform wraps these for orchestration,
> result normalization, and persistence. Do not re-implement detection logic already
> covered by a mature OSS tool.

## Crawler Layer (critical — required by all stubs)

| Tool | Repo | Why |
|------|------|-----|
| Katana | https://github.com/projectdiscovery/katana | Fast JS-aware endpoint discovery |
| ZAP Spider | https://github.com/zaproxy/zaproxy | Passive+active crawl integrated with scanning |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Scriptable proxy for auth-gated crawling |
| Playwright | https://github.com/microsoft/playwright | JS-heavy SPA crawling with real browser |
| hakrawler | https://github.com/hakluke/hakrawler | Fast passive crawl from JS/HTML links |

## Stub Mappings

### 11.01 — Missing Auth

**Detects:** API endpoints that respond to unauthenticated requests with protected data

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with token removed; flags 200 on auth-required routes |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-apis/` templates; unauthenticated endpoint checks |
| Akto | https://github.com/akto-api-security/community-edition | Auth bypass test suite for REST/GraphQL APIs |
| VulnAPI | https://github.com/cerberauth/vulnapi | JWT/OAuth unauthenticated access checks |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz API paths without auth headers; flag non-401 responses |

### 11.02 — Broken Object Level Authorization

**Detects:** IDOR — swapping object IDs returns another user's data

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | IDOR active scan rule; compares responses across sessions |
| Akto | https://github.com/akto-api-security/community-edition | BOLA/IDOR automated test engine |
| Nuclei | https://github.com/projectdiscovery/nuclei | `idor/` template pack |
| Wfuzz | https://github.com/xmendez/wfuzz | Enumerate ID ranges in path/param; flag cross-user leaks |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Two-session proxy: replay requests with swapped IDs |

### 11.03 — Over-Broad Responses

**Detects:** API responses returning more fields than the caller is authorized to see

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan flags sensitive field patterns in responses |
| Akto | https://github.com/akto-api-security/community-edition | Response-field analysis for PII / internal fields |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/` templates matching sensitive JSON keys |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script to diff response schema between privilege levels |

### 11.04 — Mass Assignment

**Detects:** POST/PUT/PATCH bodies that accept and persist privileged fields

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan injects extra fields; checks if persisted |
| Akto | https://github.com/akto-api-security/community-edition | Mass-assignment test suite |
| arjun | https://github.com/s0md3v/Arjun | Discovers undocumented request body parameters |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz JSON bodies with privileged field wordlists |
| Cherrybomb | https://github.com/blst-security/cherrybomb | OpenAPI diff — flags params not in spec |

### 11.05 — Introspection Exposure

**Detects:** GraphQL introspection enabled in production, leaking the full schema

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `graphql/graphql-introspection-*` templates |
| ZAP | https://github.com/zaproxy/zaproxy | GraphQL passive/active scanner checks introspection |
| httpx | https://github.com/projectdiscovery/httpx | Probe `/graphql` with introspection query; flag schema response |
| Akto | https://github.com/akto-api-security/community-edition | GraphQL security checks including introspection |

### 11.06 — Authorization Gaps per Resolver

**Detects:** GraphQL resolvers that skip authorization checks for specific field/query combinations

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Akto | https://github.com/akto-api-security/community-edition | Resolver-level auth test matrix |
| ZAP | https://github.com/zaproxy/zaproxy | GraphQL active scanner with multi-role session comparison |
| Nuclei | https://github.com/projectdiscovery/nuclei | `graphql/` templates probing resolver auth |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Two-session proxy comparing resolver responses by role |

### 11.07 — Query Depth Abuse

**Detects:** GraphQL accepting deeply nested queries causing resource exhaustion

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `graphql/graphql-depth-limit-*` templates |
| ZAP | https://github.com/zaproxy/zaproxy | GraphQL active scanner includes depth-bomb tests |
| Wfuzz | https://github.com/xmendez/wfuzz | Generate increasing-depth query payloads |

### 11.08 — Batching Abuse

**Detects:** GraphQL/REST batching endpoints used to bypass per-request rate limits

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `graphql/graphql-batch-*` templates |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with batch query payloads |
| Wfuzz | https://github.com/xmendez/wfuzz | Send batched query arrays; observe rate-limit bypass |

### 11.09 — Alias-Based Rate Limit Bypass

**Detects:** GraphQL aliases used to send multiple operations in one request, bypassing rate limits

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `graphql/graphql-alias-*` templates |
| ZAP | https://github.com/zaproxy/zaproxy | GraphQL scanner tests alias multiplication |
| Wfuzz | https://github.com/xmendez/wfuzz | Generate N-alias payloads for a single operation |

### 11.10 — Missing Auth on Socket Connect

**Detects:** WebSocket endpoints that accept connections without authentication

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | WebSocket passive scanner; flags unauthenticated upgrades |
| Nuclei | https://github.com/projectdiscovery/nuclei | `websocket/` templates for unauthenticated connect |
| Playwright | https://github.com/microsoft/playwright | Drive WS handshake without auth token; observe response |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept WS upgrade; strip auth header; check if accepted |

### 11.11 — Message-Level Auth Bugs

**Detects:** WebSocket messages that bypass per-message authorization checks

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | WebSocket active scanner replays messages across sessions |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and replay WS frames with modified auth context |
| Playwright | https://github.com/microsoft/playwright | Script message-level auth probe via browser WS client |

### 11.12 — Cross-User Message Access

**Detects:** WebSocket channels leaking messages intended for a different user

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Multi-session WS comparison for cross-user message leaks |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Two-session proxy; compare message streams by user |
| Playwright | https://github.com/microsoft/playwright | Two-browser-context test; observe cross-user message delivery |

### 11.13 — Exposed Debug Endpoints

**Detects:** Debug, admin, or internal routes left accessible in production

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-panels/` + `misconfiguration/` templates |
| Nikto | https://github.com/sullo/nikto | Broad check for debug/admin path patterns |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz with debug-endpoint wordlists (actuator, debug, trace) |
| dirsearch | https://github.com/maurosoria/dirsearch | Built-in debug/admin path wordlist |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive discovery of `/actuator`, `/_debug`, `/admin` |

### 11.14 — Reflection Exposure

**Detects:** API responses that echo back internal stack traces, framework details, or server info

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive scanner flags stack traces and server banners |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/tokens/` + `misconfiguration/` error-disclosure templates |
| Nikto | https://github.com/sullo/nikto | Server header and error-page fingerprinting |

### 11.15 — Weak Service Auth

**Detects:** gRPC/internal services using weak or absent mutual authentication

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `network/` + `misconfiguration/` templates for service auth |
| Tsunami | https://github.com/google/tsunami-security-scanner | Plugin-based infra scanner; checks exposed service auth |
| httpx | https://github.com/projectdiscovery/httpx | Probe gRPC/HTTP2 endpoints for auth requirements |

### 11.16 — Old Vulnerable Versions

**Detects:** API frameworks or dependencies with known CVEs still running in production

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `cves/` template library — thousands of version-fingerprint CVE checks |
| Nikto | https://github.com/sullo/nikto | Version fingerprinting + CVE lookup |
| Tsunami | https://github.com/google/tsunami-security-scanner | Plugin library for infra-level CVE detection |
| httpx | https://github.com/projectdiscovery/httpx | Header/banner fingerprinting for version extraction |

### 11.17 — Deprecated Endpoints Still Active

**Detects:** Old API versions (v1, legacy routes) still reachable and potentially unpatched

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Fuzz versioned path prefixes (`/v1/`, `/v2/`, `/api/old/`) |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive enum across version namespaces |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-apis/` templates targeting legacy version paths |
