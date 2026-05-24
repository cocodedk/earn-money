# OSS Tool Mapping — Phase 16: CORS and Cross-Origin Policy

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

### 16.01 — Wildcard Origins with Credentials

**Detects:** `Access-Control-Allow-Origin: *` combined with `Access-Control-Allow-Credentials: true`, which browsers reject but misconfigured proxies may not enforce.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| CORScanner | https://github.com/chenjj/CORScanner | Dedicated CORS scanner; flags wildcard + credentials combination |
| YA-CORS | https://github.com/0x-Apollyon/YA-CORS | Automated CORS policy tester; detects wildcard misconfigurations |
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | Passive CORS misconfiguration rule; flags `*` + credentials header combo |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `cors-misconfiguration`; checks response headers on all endpoints |

### 16.02 — Origin Reflection

**Detects:** Server echoes arbitrary `Origin` header value back in `Access-Control-Allow-Origin`, allowing any domain to read credentialed responses.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| CORScanner | https://github.com/chenjj/CORScanner | Core detection: sends attacker origin, checks if reflected verbatim |
| YA-CORS | https://github.com/0x-Apollyon/YA-CORS | Sends multiple crafted origins; flags reflection with credentials |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `cors-arbitrary-origin-trusted`; reflection check with credentials |
| ZAP | https://github.com/zaproxy/zaproxy | Active CORS scan; injects arbitrary origin and inspects ACAO response header |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Inject arbitrary `Origin` headers; inspect `Access-Control-Allow-Origin` response |

### 16.03 — Null Origin Trust

**Detects:** Server returns `Access-Control-Allow-Origin: null`, which sandboxed iframes or `data:` URIs can exploit.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| CORScanner | https://github.com/chenjj/CORScanner | Sends `Origin: null`; flags `ACAO: null` + credentials in response |
| YA-CORS | https://github.com/0x-Apollyon/YA-CORS | Null-origin test case in default scan profile |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `cors-null-origin-reflected`; header pattern match |
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | Passive rule detects null origin allowance in response headers |

### 16.04 — Over-Trusted Subdomains

**Detects:** CORS policy trusts entire `*.example.com` wildcard or specific subdomains that can be taken over.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| CORScanner | https://github.com/chenjj/CORScanner | Tests subdomain-based origins; flags overly broad subdomain trust |
| YA-CORS | https://github.com/0x-Apollyon/YA-CORS | Probes with crafted subdomain origins; detects prefix/suffix matches |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates: send `evil.trusted-domain.com` origin; check ACAO reflection |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with subdomain origin variants; inspect ACAO header |

### 16.05 — Over-Exposed Headers

**Detects:** `Access-Control-Expose-Headers` reveals sensitive internal headers (auth tokens, internal IDs, tracing headers).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | Passive rule inspects `ACEH` value for sensitive header names |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom template: regex match `Access-Control-Expose-Headers` for patterns like `Authorization`, `X-Internal-*` |
| CORScanner | https://github.com/chenjj/CORScanner | Reports full CORS header set including exposed header list |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Passively log and analyze all CORS-related response headers across crawled endpoints |

### 16.06 — Misconfigured Preflight Behavior

**Detects:** Preflight (`OPTIONS`) response grants broader permissions than actual request handlers enforce, or preflight is skipped incorrectly.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| CORScanner | https://github.com/chenjj/CORScanner | Issues OPTIONS requests; compares preflight grants vs actual response policy |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan sends OPTIONS preflight; validates `ACAM`/`ACAH` headers |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `cors-preflight-*`; checks `Access-Control-Allow-Methods` permissiveness |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz `Access-Control-Request-Method` and `Access-Control-Request-Headers` in OPTIONS; flag unexpected approvals |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Send crafted OPTIONS preflight; compare granted methods/headers vs actual enforcement |
