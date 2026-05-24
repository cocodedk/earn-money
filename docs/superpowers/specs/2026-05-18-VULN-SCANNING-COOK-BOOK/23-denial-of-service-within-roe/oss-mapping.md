# OSS Tool Mapping — Phase 23: Denial of Service Within RoE

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

### 23.01 — Expensive Search Queries

**Detects:** Search endpoints that allow unbounded queries causing excessive CPU/DB load.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with large/nested search payloads to measure response latency |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz search parameters with deeply nested or wildcard patterns |
| Wapiti | https://github.com/wapiti-scanner/wapiti | DAST module for resource-intensive input discovery |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates probing search endpoints with known expensive patterns |

### 23.02 — Large File Upload Processing

**Detects:** Upload handlers that process arbitrarily large files synchronously, exhausting memory/CPU.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with oversized file uploads to measure hang/timeout |
| Wapiti | https://github.com/wapiti-scanner/wapiti | File upload module supports large payload injection |
| Ffuf | https://github.com/ffuf/ffuf | Sends large bodies to upload endpoints to test limits |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for upload endpoints lacking size validation |

### 23.03 — Regex Backtracking

**Detects:** Server-side regex patterns vulnerable to catastrophic backtracking (ReDoS).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan injects ReDoS payloads in string inputs |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Module sends regex-exploiting strings and measures latency |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz text fields with exponential backtracking payloads |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates with known ReDoS patterns for common frameworks |

### 23.04 — GraphQL Query Depth

**Detects:** GraphQL endpoints without query depth/complexity limits, allowing deeply nested queries.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| graphql-cop | https://github.com/dolevf/graphql-cop | Directive overloading and depth-abuse checks; produces DoS-triggering query patterns |
| ZAP | https://github.com/zaproxy/zaproxy | GraphQL support in active scan; sends deeply nested queries |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for GraphQL introspection and depth-abuse patterns |
| Ffuf | https://github.com/ffuf/ffuf | POST crafted deeply-nested GraphQL queries to measure impact |
| InQL | https://github.com/doyensec/inql | GraphQL-specialist: schema introspection, depth-unbounded query generation, complexity-abuse test cases (standalone CLI or Burp) |

### 23.05 — Pagination Abuse

**Detects:** API endpoints where pagination parameters can request arbitrarily large page sizes.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan fuzzes page/limit/offset params with extreme values |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz per_page/limit params with large integer values |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for unvalidated pagination parameter patterns |
| Wapiti | https://github.com/wapiti-scanner/wapiti | DAST integer fuzzing on query parameters |

### 23.06 — Resource-Heavy Report Generation

**Detects:** Report/export endpoints that spawn expensive backend jobs without rate limiting.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan triggers report endpoints repeatedly to find limits |
| Ffuf | https://github.com/ffuf/ffuf | Concurrent requests to report endpoints to detect abuse potential |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for report/export endpoints lacking rate controls |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script concurrent report requests and observe server behaviour |

### 23.07 — Rate Limit Gaps

**Detects:** Authentication, API, or action endpoints missing rate limiting or with bypassable limits.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan sends rapid repeated requests and checks for 429 responses |
| Ffuf | https://github.com/ffuf/ffuf | High-rate fuzzing to probe rate limit enforcement |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for rate-limit absence on login/reset/API endpoints |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Module for brute-force and rate-limit bypass testing |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script header rotation to test IP-based rate limit bypass |
