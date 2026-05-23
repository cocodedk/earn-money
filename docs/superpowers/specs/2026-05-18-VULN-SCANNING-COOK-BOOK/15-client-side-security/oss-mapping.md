# OSS Tool Mapping — Phase 15: Client-Side Security

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

### 15.01 — API Keys in Client-Side Code

**Detects:** Hardcoded API keys/secrets embedded in JS bundles or HTML.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| truffleHog | https://github.com/trufflesecurity/trufflehog | Scans HTTP responses and JS files for high-entropy secrets and known key patterns |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `exposed-api-key-*`; regex-based JS/HTML response scanning |
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | Passive scan rule `Information Disclosure - Suspicious Comments` + secret patterns |
| Retire.js | https://github.com/RetireJS/retire.js | Flags JS files for audit; pairs with secret scanners |

### 15.02 — Hidden Endpoints

**Detects:** Undocumented or commented-out endpoints reachable via JS analysis or path guessing.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Katana | https://github.com/projectdiscovery/katana | JS parsing mode extracts endpoints from `fetch`/`axios`/XHR calls |
| Ffuf | https://github.com/ffuf/ffuf | Content discovery against extracted endpoint wordlists |
| hakrawler | https://github.com/hakluke/hakrawler | Extracts URLs from JS source and HTML comments |
| ParamSpider | https://github.com/devanshbatham/ParamSpider | Mines parameters and paths from JS files |
| Playwright | https://github.com/microsoft/playwright | Intercepts network calls during full SPA execution to log hidden endpoints |

### 15.03 — Feature Flags Exposed Client-Side

**Detects:** Feature flag configs or toggle states exposed in JS that reveal unreleased features.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates matching feature-flag JSON patterns in responses |
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan captures flag payloads in responses |
| Playwright | https://github.com/microsoft/playwright | Intercept JS config objects exposing flag state during app boot |
| truffleHog | https://github.com/trufflesecurity/trufflehog | Detects high-value config objects in JS responses |

### 15.04 — Internal Routes Exposed

**Detects:** Admin or internal-only routes accessible or discoverable from client-side JS.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Katana | https://github.com/projectdiscovery/katana | Extracts route definitions from React Router / Vue Router bundles |
| Ffuf | https://github.com/ffuf/ffuf | Brute-force discovered route list; check for 200/302 on unauthenticated requests |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `admin-panel-*`, `exposed-admin-*` |
| hakrawler | https://github.com/hakluke/hakrawler | Crawls and surfaces internal-looking path patterns |

### 15.05 — Source Code Leakage

**Detects:** Source maps, `.git`, unminified source, or backup files served publicly.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `exposed-git-*`, `sourcemap-*`, `backup-files-*` |
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | `.git` folder and source map passive detection rules |
| Ffuf | https://github.com/ffuf/ffuf | Wordlist of common leak paths (`/.git/HEAD`, `*.map`, `*.bak`) |
| W3af | https://github.com/andresriancho/w3af | `source_code_disclosure` plugin |

### 15.06 — Comments and TODOs Revealing Sensitive Info

**Detects:** HTML/JS comments disclosing internal notes, endpoints, credentials, or TODOs.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | Passive rule: `Information Disclosure - Suspicious Comments` |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates regex-matching `TODO`/`FIXME`/`password`/`secret` in comments |
| Katana | https://github.com/projectdiscovery/katana | Captures raw HTML including comment blocks for inline analysis |
| hakrawler | https://github.com/hakluke/hakrawler | Captures raw HTML including comment blocks for downstream analysis |

### 15.07 — Missing Origin Checks (postMessage)

**Detects:** `window.addEventListener('message')` handlers that don't validate `event.origin`.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Playwright | https://github.com/microsoft/playwright | Send crafted `postMessage` from attacker origin; observe DOM mutations |
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | Passive scan for unguarded `message` event listeners |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom template: regex on JS source for `addEventListener.*message` without origin guard |

### 15.08 — Unsafe Message Handling

**Detects:** `postMessage` or BroadcastChannel data processed without sanitization, enabling XSS or logic abuse.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Domdig | https://github.com/fcavallarin/domdig | Traces data flow from message handlers to DOM sinks |
| Playwright | https://github.com/microsoft/playwright | Inject XSS payloads via `postMessage`; observe DOM execution |
| ZAP | https://github.com/zaproxy/zaproxy | DOM XSS active scan probes message-based sinks |

### 15.09 — Tokens Stored Unsafely

**Detects:** Auth tokens (JWT, session) stored in `localStorage`/`sessionStorage` instead of `HttpOnly` cookies.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Playwright | https://github.com/microsoft/playwright | Post-login JS `localStorage` / `sessionStorage` inspection for token presence |
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | Passive rule flags JWT patterns in storage or non-HttpOnly cookies |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `jwt-in-localstorage`; JS response regex for storage writes |

### 15.10 — Sensitive User Data Exposed Client-Side

**Detects:** PII or sensitive fields (SSN, full card numbers, passwords) returned in API responses and stored client-side.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan rule `Information Disclosure - Sensitive Information in HTTP Referrer Header` + PII patterns |
| truffleHog | https://github.com/trufflesecurity/trufflehog | Regex patterns for PII in HTTP response bodies |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates matching SSN/card-number patterns in API responses |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept all responses; script applies PII regex across payloads |

### 15.11 — Hidden UI Controls

**Detects:** DOM elements hidden via CSS (`display:none`, `visibility:hidden`) that expose privileged actions when revealed.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Playwright | https://github.com/microsoft/playwright | Enumerate hidden elements; toggle visibility; probe resulting API calls |
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | DOM passive scan surfaces hidden form fields and controls |
| Domdig | https://github.com/fcavallarin/domdig | Analyzes DOM for hidden interactive elements |

### 15.12 — Disabled Buttons with Exposed APIs

**Detects:** UI buttons disabled client-side while the underlying API endpoint remains fully functional.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Playwright | https://github.com/microsoft/playwright | Remove `disabled` attribute; click button; observe API call; replay directly |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan replays discovered endpoints bypassing client-side gating |
| Ffuf | https://github.com/ffuf/ffuf | Direct endpoint fuzzing extracted from JS, bypassing UI state |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and replay requests that the UI suppresses for non-privileged users |
