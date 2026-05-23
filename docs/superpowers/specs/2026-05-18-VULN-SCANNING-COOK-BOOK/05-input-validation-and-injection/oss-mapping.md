# OSS Tool Mapping — Phase 05: Input Validation and Injection

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
| arjun | https://github.com/s0md3v/Arjun | HTTP parameter discovery before injection |

## Stub Mappings

### 5.01 — Classic SQLi

**Detects:** Error-based and UNION-based SQL injection in HTTP parameters

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Sqlmap | https://github.com/sqlmapproject/sqlmap | Full error/union/boolean detection; `--level`/`--risk` controls |
| Ghauri | https://github.com/r0oth3x49/ghauri | Faster alternative; handles modern WAF evasion |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule `40018` (SQL injection) |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module sql` covers classic patterns |

### 5.02 — Blind SQLi

**Detects:** Boolean-blind and time-based blind SQL injection

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Sqlmap | https://github.com/sqlmapproject/sqlmap | `--technique=BT`; time-based with adaptive delays |
| Ghauri | https://github.com/r0oth3x49/ghauri | Boolean/time-blind with lower false-positive rate |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule `40020` (blind SQL injection) |

### 5.03 — Second-Order SQLi

**Detects:** Stored input later interpolated unsafely into a query

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Sqlmap | https://github.com/sqlmapproject/sqlmap | `--second-url` for second-order trigger point |
| ZAP | https://github.com/zaproxy/zaproxy | Manual scripted scan; no native second-order rule |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Multi-request module covers some stored patterns |

### 5.04 — ORM / Query-Builder Injection

**Detects:** Injection through ORM filter/order arguments or raw-query escapes

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Sqlmap | https://github.com/sqlmapproject/sqlmap | Fuzz ORM-exposed params same as raw SQL |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates for Django/Hibernate known patterns |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan covers parameterised endpoints |

### 5.05 — Mongo-Style Operator Injection

**Detects:** `$where`, `$gt`, `$regex` operator injection in JSON bodies

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| NoSQLMap | https://github.com/codingo/NoSQLMap | Primary tool for MongoDB operator injection |
| Wfuzz | https://github.com/xmendez/wfuzz | JSON body fuzzing with operator payloads |
| Nuclei | https://github.com/projectdiscovery/nuclei | `nosqli` tagged templates in nuclei-templates |

### 5.06 — JSON Query Manipulation

**Detects:** Manipulation of JSON-native query APIs (e.g. GraphQL, OData filters)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Wfuzz | https://github.com/xmendez/wfuzz | JSON body payloads via `--data` with fuzzing |
| ZAP | https://github.com/zaproxy/zaproxy | GraphQL active scan via zap-extensions GraphQL add-on |
| Nuclei | https://github.com/projectdiscovery/nuclei | GraphQL injection templates in nuclei-templates |
| ffuf | https://github.com/ffuf/ffuf | JSON field fuzzing with custom wordlists |

### 5.07 — Shell Command Execution Through Parameters

**Detects:** OS command injection via HTTP parameters reaching shell calls

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Commix | https://github.com/commixproject/commix | Purpose-built OS command injection; multiple techniques |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule `90020` (command injection) |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module exec` for command injection patterns |
| Nuclei | https://github.com/projectdiscovery/nuclei | `rce` tagged templates with OOB detection |

### 5.08 — Unsafe System Calls

**Detects:** Parameters that reach `exec`, `popen`, `subprocess` without sanitisation

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Commix | https://github.com/commixproject/commix | Covers both argument-injection and shell-metachar paths |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule `90020` |
| Nuclei | https://github.com/projectdiscovery/nuclei | OOB-confirmed RCE templates |

### 5.09 — Template Expression Injection

**Detects:** SSTI via `{{7*7}}` style expressions in Jinja2, Twig, Freemarker, etc.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Tplmap | https://github.com/epinna/tplmap | Primary SSTI tool; engine fingerprint + exploitation |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule `90035` (SSTI) |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssti` tagged templates for common engines |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module ssti` module |

### 5.10 — Sandbox Escape Risk

**Detects:** Sandbox breakout patterns in template engines or eval contexts

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Tplmap | https://github.com/epinna/tplmap | Sandbox-escape payloads for Jinja2/Mako/Pebble |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom OOB-confirmed templates for eval contexts |

### 5.11 — Directory Query Injection (LDAPi / XPath)

**Detects:** LDAP filter injection and XPath query injection

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rules `90017` (XPath) and `40015` (LDAP) |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module ldap` and `--module xpath` |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ldap-injection` / `xpath-injection` templates |

### 5.12 — XML Parser Abuse (XXE)

**Detects:** External entity injection, entity expansion (billion-laughs), DTD abuse

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule `90023` (XXE) |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module xxe` |
| Nuclei | https://github.com/projectdiscovery/nuclei | `xxe` tagged OOB and error-based templates |
| W3af | https://github.com/andresriancho/w3af | `xml_injection` plugin |

### 5.13 — Response Splitting (CRLF)

**Detects:** HTTP response-splitting via `\r\n` injection in headers or redirects

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule `10005` (CRLF injection) |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module crlf` |
| Nuclei | https://github.com/projectdiscovery/nuclei | `crlf-injection` templates |
| ffuf | https://github.com/ffuf/ffuf | Header-value fuzzing with CRLF wordlists |

### 5.14 — Cache Poisoning Helpers

**Detects:** Inputs that influence cache keys or cache-control headers maliciously

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Param Miner (ZAP) | https://github.com/zaproxy/zap-extensions | Header/param cache-poisoning probes |
| Nuclei | https://github.com/projectdiscovery/nuclei | `cache-poisoning` templates |
| ffuf | https://github.com/ffuf/ffuf | Header fuzzing for unkeyed inputs |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and mutate cache headers |

### 5.15 — Mail Header Injection

**Detects:** Newline injection in `To`/`From`/`Subject` fields reaching SMTP

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule `10098` (email header injection) |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Covers form fields with CRLF + SMTP payloads |
| Nuclei | https://github.com/projectdiscovery/nuclei | `email-injection` templates |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz contact/subscribe forms with CRLF payloads |

### 5.16 — Notification Template Abuse

**Detects:** User-controlled template fragments in notification systems enabling SSTI or content injection

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Tplmap | https://github.com/epinna/tplmap | SSTI via notification preview endpoints |
| ZAP | https://github.com/zaproxy/zaproxy | Passive detection of reflected template markers |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssti` + custom notification-context templates |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz template fields with expression payloads |
