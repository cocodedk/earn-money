# OSS Tool Mapping — Phase 17: HTTP Request/Response Handling

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

### 17.01 — HTTP Request Smuggling

**Detects:** Desync between front-end proxy and back-end server on `Content-Length` / `Transfer-Encoding` handling.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| smuggler | https://github.com/defparam/smuggler | CL.TE, TE.CL, TE.TE probes; primary detection tool |
| h2csmuggler | https://github.com/BishopFox/h2csmuggler | H2C upgrade-based smuggling path |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule for chunked encoding desync |
| Wfuzz | https://github.com/xmendez/wfuzz | Custom payload fuzzing for edge-case variants |

### 17.02 — HTTP Response Splitting

**Detects:** CR/LF injection in redirect or header-setting endpoints allowing response injection.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 10098 (CRLF injection) |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module crlf` CRLF injection module |
| Wfuzz | https://github.com/xmendez/wfuzz | `%0d%0a` payloads in header-reflected params |
| Nuclei | https://github.com/projectdiscovery/nuclei | CRLF-injection templates in nuclei-templates |

### 17.03 — Host Header Attacks

**Detects:** Password-reset poisoning, cache poisoning, and SSRF via manipulated `Host` / `X-Forwarded-Host`.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Host header scan rule (active); extensions add more |
| Nuclei | https://github.com/projectdiscovery/nuclei | `host-header-injection` template family |
| httpx | https://github.com/projectdiscovery/httpx | Probe with custom Host values; observe redirects |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz Host / X-Forwarded-Host with wordlists |

### 17.04 — Cache Poisoning

**Detects:** Unkeyed header or parameter causes poisoned cache entry served to other users.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Cache poisoning active scan rules |
| Nuclei | https://github.com/projectdiscovery/nuclei | `cache-poisoning` templates |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Scriptable; inject unkeyed headers, observe `Age` |
| Wfuzz | https://github.com/xmendez/wfuzz | Enumerate unkeyed header candidates |

### 17.05 — Web Cache Deception

**Detects:** Static-extension path tricks (`/profile/photo.css`) cause dynamic responses to be cached publicly.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `web-cache-deception` templates |
| ZAP | https://github.com/zaproxy/zaproxy | Custom active scan script for extension appending |
| Wfuzz | https://github.com/xmendez/wfuzz | Append `.css/.js/.png` to authenticated endpoints |
| httpx | https://github.com/projectdiscovery/httpx | Observe `Cache-Control` / `Age` on crafted paths |

### 17.06 — Content-Type Confusion

**Detects:** Server ignores client `Content-Type` leading to misparse, XSS, or deserialization gadgets.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan varies `Content-Type` on POST bodies |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Mutates content-type headers on known endpoints |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz `Content-Type` values on upload/API endpoints |
| Nikto | https://github.com/sullo/nikto | Flags MIME-sniffing misconfiguration |

### 17.07 — Method Override Abuse

**Detects:** `X-HTTP-Method-Override` / `_method` parameter bypasses method-level access controls.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Method override active scan rule |
| Nuclei | https://github.com/projectdiscovery/nuclei | `http-method-override` templates |
| Wfuzz | https://github.com/xmendez/wfuzz | Inject override headers on all endpoints |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and rewrite method headers in-flight |

### 17.08 — Parameter Pollution

**Detects:** Duplicate parameters (`?id=1&id=2`) cause server/WAF disagreement exploitable for bypass or injection.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Parameter pollution scan rule |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Duplicate param injection in module set |
| Wfuzz | https://github.com/xmendez/wfuzz | Duplicate and multi-value param fuzzing |
| W3af | https://github.com/andresriancho/w3af | `http_response_body_contains` plugin detects split |
