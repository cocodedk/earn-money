# OSS Tool Mapping — Phase 07: CSRF and Browser-Side Request Abuse

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

### 7.01 — State-Changing Requests Without CSRF Protection

**Detects:** POST/PUT/DELETE endpoints with no CSRF token, Origin check, or SameSite cookie

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 20012 (CSRF); passive rule 10202 (Anti-CSRF tokens) |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module csrf` identifies missing token on state-changing forms |
| Nuclei | https://github.com/projectdiscovery/nuclei | `csrf` tagged templates for common frameworks |
| W3af | https://github.com/andresriancho/w3af | `csrf` plugin covers form-based and AJAX state changes |

### 7.02 — Weak CSRF Token Validation

**Detects:** CSRF tokens that are accepted when empty, guessable, or from another user

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 20012 with token-stripping variants |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz token parameter with empty, short, and static values |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script to replay requests with modified/removed token |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Tests token removal and static-value bypass |

### 7.03 — Token Not Tied to Session

**Detects:** CSRF token accepted regardless of which session generated it

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with dual-session token cross-use |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script: capture token from session A, replay in session B |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates for cross-session token acceptance |

### 7.04 — SameSite Bypass Conditions

**Detects:** SameSite=Lax bypasses via top-level navigation GET or sub-domain misuse

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10054 (cookie SameSite attribute check) |
| Nuclei | https://github.com/projectdiscovery/nuclei | `samesite` cookie attribute templates |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Inspect Set-Cookie headers for missing SameSite |
| Playwright | https://github.com/microsoft/playwright | Cross-site navigation PoC to confirm Lax bypass |

### 7.05 — Login CSRF

**Detects:** Login form lacks CSRF protection, enabling session fixation via forced login

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 20012 on login endpoint |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module csrf` on login form |
| Nuclei | https://github.com/projectdiscovery/nuclei | `login-csrf` templates |

### 7.06 — GraphQL CSRF

**Detects:** GraphQL mutations accepted via GET or simple-request POST without CSRF defence

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | GraphQL add-on (zap-extensions) + active CSRF rule |
| Nuclei | https://github.com/projectdiscovery/nuclei | `graphql-csrf` and `graphql-introspection` templates |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz GraphQL endpoint with content-type variations |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Replay mutations without auth headers / CSRF tokens |

### 7.07 — CORS-Assisted CSRF-Style Abuse

**Detects:** Permissive CORS that enables cross-origin reads of credentialed responses

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| CORScanner | https://github.com/chenjj/CORScanner | Primary tool for CORS misconfiguration detection |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40040 (CORS) |
| Nuclei | https://github.com/projectdiscovery/nuclei | `cors-misconfiguration` templates |
| YA-CORS | https://github.com/0x-Apollyon/YA-CORS | CORS misconfiguration scanner with origin reflection checks |
