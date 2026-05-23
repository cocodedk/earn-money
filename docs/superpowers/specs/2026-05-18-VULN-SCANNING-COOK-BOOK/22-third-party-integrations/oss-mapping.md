# OSS Tool Mapping — Phase 22: Third-Party Integrations

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

### 22.01 — Webhook Abuse

**Detects:** Webhook endpoints that can be triggered by unauthorized parties or lack signature validation.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for missing HMAC/signature checks on webhook routes |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates probing webhook endpoints without auth headers |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz webhook endpoints with crafted payloads |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and replay webhook requests to test validation |
| Wapiti | https://github.com/wapiti-scanner/wapiti | DAST module for unauthenticated POST endpoint abuse |

### 22.02 — OAuth App Misconfiguration

**Detects:** OAuth flows with open redirects, missing state param, or over-broad scopes.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| VulnAPI | https://github.com/cerberauth/vulnapi | JWT/OAuth fuzzer; tests redirect_uri and state validation |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for open redirect in OAuth callback |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for OAuth misconfiguration patterns |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept OAuth flows to inspect/tamper parameters |

### 22.03 — Payment Provider Callback Tampering

**Detects:** Payment callback endpoints that trust client-supplied amounts or status without server-side verification.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for parameter tampering on callback routes |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz amount/status/currency fields in callback requests |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept payment callbacks; modify fields and replay |
| Wapiti | https://github.com/wapiti-scanner/wapiti | DAST module for parameter manipulation |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for payment endpoint mass-assignment patterns |

### 22.04 — SAML Misconfiguration

**Detects:** SAML authentication flaws including XML signature wrapping, unvalidated assertions, or replay attacks.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | SAML passive scan and active assertion manipulation |
| VulnAPI | https://github.com/cerberauth/vulnapi | Covers auth protocol fuzzing including SAML vectors |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for common SAML endpoint misconfigs |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and modify SAML assertions in transit |

### 22.05 — Email/SMS Provider Abuse

**Detects:** Messaging endpoints usable by unauthenticated or low-privilege actors for spam/abuse.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for rate-limit absence on messaging endpoints |
| Ffuf | https://github.com/ffuf/ffuf | Flood messaging endpoints to detect missing rate limits |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for exposed email/SMS trigger endpoints |
| Wapiti | https://github.com/wapiti-scanner/wapiti | DAST for unauthenticated form/action endpoints |

### 22.06 — Unsafe Import/Export Integrations

**Detects:** File import/export features that process untrusted content without sanitization (CSV injection, XML bombs, etc.).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan uploads malformed files to import endpoints |
| Wapiti | https://github.com/wapiti-scanner/wapiti | File upload module with injection payloads |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz import endpoints with malformed file contents |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for CSV injection and XML bomb patterns |

### 22.07 — Trusting Third-Party Callback Data Without Verification

**Detects:** App logic that uses data from third-party callbacks as authoritative without independent verification.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for parameter pollution on callback routes |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept third-party callbacks; inject/modify data fields |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz callback body fields with tampered values |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates targeting callback endpoints with spoofed data |
| Wapiti | https://github.com/wapiti-scanner/wapiti | DAST module for trust-boundary issues in POST handlers |
