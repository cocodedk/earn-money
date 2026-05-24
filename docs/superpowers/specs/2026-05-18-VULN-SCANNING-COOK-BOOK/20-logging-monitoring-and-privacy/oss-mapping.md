# OSS Tool Mapping — Phase 20: Logging, Monitoring and Privacy

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

### 20.01 — Sensitive Data in Logs

**Detects:** API responses or debug endpoints exposing log entries containing PII, tokens, or credentials.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10027 flags suspicious developer comments; custom passive script needed for PII/token pattern matching in log endpoints |
| truffleHog | https://github.com/trufflesecurity/trufflehog | Secret/PII pattern matching in crawled response content |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates probing sensitive data in log endpoints |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Proxy script to flag PII patterns in all responses |
| Katana | https://github.com/projectdiscovery/katana | Discover `/logs`, `/debug`, `/admin/logs` endpoints |

### 20.02 — Secrets in Error Responses

**Detects:** Stack traces, DB connection strings, API keys, or internal paths leaked in HTTP error responses.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10023 (debug error messages from ASP.NET/IIS/Apache); active scan to trigger server errors and inspect responses |
| Nikto | https://github.com/sullo/nikto | Triggers error conditions; inspects responses for info leakage |
| Nuclei | https://github.com/projectdiscovery/nuclei | `error-disclosure` / `stack-trace-disclosure` templates |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Error-handling module probes and inspects verbose errors |
| truffleHog | https://github.com/trufflesecurity/trufflehog | Secret patterns in error response bodies |

### 20.03 — PII Overexposure

**Detects:** API endpoints returning fields (email, phone, SSN, etc.) beyond what the consumer needs.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan of response bodies for PII patterns |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script to flag PII in JSON/XML response fields |
| Nuclei | https://github.com/projectdiscovery/nuclei | `pii-disclosure` templates |
| truffleHog | https://github.com/trufflesecurity/trufflehog | PII regex patterns across crawled responses |
| Katana | https://github.com/projectdiscovery/katana | Enumerate all API endpoints for full-response inspection |

### 20.04 — Insecure Analytics / Debug Tooling

**Detects:** Publicly exposed debug UIs (phpMyAdmin, Kibana, Grafana, Django debug toolbar) or analytics beacons leaking data.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-panels` template family (Kibana, Grafana, etc.) |
| Nikto | https://github.com/sullo/nikto | Fingerprints well-known admin/debug paths |
| httpx | https://github.com/projectdiscovery/httpx | Probe known debug/admin endpoint wordlist |
| ZAP | https://github.com/zaproxy/zaproxy | Spider + passive detection of debug-mode indicators |
| Katana | https://github.com/projectdiscovery/katana | Discover analytics script inclusions in crawled pages |

### 20.05 — Audit Log Tampering

**Detects:** Ability to delete, overwrite, or forge audit log entries via application endpoints.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with DELETE/PUT on log resource endpoints |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz log ID parameters with DELETE/PATCH methods |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and replay mutated log-write requests |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates for log mutation endpoints |

### 20.06 — Missing Audit Trail for Sensitive Actions

**Detects:** High-value actions (login, privilege escalation, data export) that produce no auditable event.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan exercises sensitive endpoints; compare log output |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script to perform actions and poll log endpoint for entries |
| Playwright | https://github.com/microsoft/playwright | Automate sensitive UI actions; assert log endpoint responds |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates probing sensitive action endpoints for missing audit entries |

### 20.07 — Log Injection

**Detects:** User-controlled input written unsanitised into logs enabling log forging or log4shell-style gadgets.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active rule injects CRLF and log-format sequences in all inputs |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Log injection module (newline injection in params) |
| Wfuzz | https://github.com/xmendez/wfuzz | Payload list with `\n`, `\r\n`, `${jndi:...}` log4shell probes |
| Nuclei | https://github.com/projectdiscovery/nuclei | `log4j-rce` + `log-injection` template families |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept all inputs; inject log-format sequences systematically |
