# OSS Tool Mapping — Phase 19: Cryptography and Secrets

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

### 19.01 — Hardcoded Secrets

**Detects:** API keys, tokens, or credentials embedded in JS bundles, HTML source, or HTTP responses.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| truffleHog | https://github.com/trufflesecurity/trufflehog | Secret scanning in responses, JS files, and git history |
| gitleaks | https://github.com/gitleaks/gitleaks | Regex + entropy-based secret detection in source |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-tokens` / `hardcoded-secrets` templates |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10027 (information disclosure — suspicious comments) |
| Katana | https://github.com/projectdiscovery/katana | Crawl JS files; pipe to truffleHog |

### 19.02 — Weak Token Generation

**Detects:** Session tokens, CSRF tokens, or password-reset tokens with insufficient entropy.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Token analysis tool (Fuzzer → token strength analysis) |
| Wfuzz | https://github.com/xmendez/wfuzz | Collect token samples for offline entropy analysis |
| Nuclei | https://github.com/projectdiscovery/nuclei | `weak-token-generation` templates |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept tokens across many requests; export for analysis |

### 19.03 — Predictable IDs

**Detects:** Sequential or low-entropy object IDs enabling enumeration / IDOR.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | IDOR active scan via ID enumeration |
| Wfuzz | https://github.com/xmendez/wfuzz | Numeric/sequential ID fuzzing on object endpoints |
| Nuclei | https://github.com/projectdiscovery/nuclei | `idor` and `predictable-id` templates |
| W3af | https://github.com/andresriancho/w3af | Integer enumeration plugin |

### 19.04 — Weak Random Values

**Detects:** Nonces, salts, or challenge values with low entropy or deterministic seeding.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Fuzzer collects random values for entropy measurement |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script to collect and analyse nonce distributions |
| Wfuzz | https://github.com/xmendez/wfuzz | Harvest challenge/nonce values across many sessions |
| Nuclei | https://github.com/projectdiscovery/nuclei | `weak-random` detection templates |

### 19.05 — Sensitive Data in URLs

**Detects:** Tokens, passwords, or PII transmitted in query strings (logged by proxies, referrers, etc.).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10024 (sensitive data in URL) |
| Nuclei | https://github.com/projectdiscovery/nuclei | `sensitive-data-in-url` templates |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script to flag credential-like params in query strings |
| httpx | https://github.com/projectdiscovery/httpx | Probe and log full request URLs for analysis |
| Katana | https://github.com/projectdiscovery/katana | Crawl and capture all URLs including params |

### 19.06 — Insecure Password Storage Hints

**Detects:** Error messages, timing differences, or responses revealing weak hashing (MD5, SHA-1, unsalted).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule scans error messages for hash-related disclosure |
| Nuclei | https://github.com/projectdiscovery/nuclei | `password-hash-disclosure` templates |
| Wfuzz | https://github.com/xmendez/wfuzz | Timing-attack probes on login endpoints |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept login responses; inspect hash format leaks in verbose error messages |

### 19.07 — Weak Encryption Mode

**Detects:** Use of ECB mode, deprecated ciphers, or broken TLS configurations in transport or application layer.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| testssl.sh | https://github.com/drwetter/testssl.sh | Comprehensive TLS cipher suite and protocol analysis |
| SSLyze | https://github.com/nabla-c0d3/sslyze | Python-native TLS scanner; programmable API for runner integration; cipher suite, protocol version, and known-vuln checks |
| O-Saft | https://github.com/OWASP/O-Saft | TLS/SSL weakness analysis, OWASP-maintained |
| ZAP | https://github.com/zaproxy/zaproxy | TLS passive checks; active scan for weak cipher negotiation |
| Nuclei | https://github.com/projectdiscovery/nuclei | `deprecated-tls` / `weak-cipher` templates |
| Nikto | https://github.com/sullo/nikto | TLS version and cipher checks |

### 19.08 — Missing Signing or Integrity Checks

**Detects:** Unsigned JWTs, missing subresource integrity (SRI), or unsigned API payloads.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| jwt_tool | https://github.com/ticarpi/jwt_tool | Dedicated JWT attack tool: alg:none (`-X a`), key confusion (`-X k`), signature stripping |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rules for JWT `alg:none` and missing SRI |
| Nuclei | https://github.com/projectdiscovery/nuclei | `jwt-none-algorithm` + `missing-sri` templates |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script to intercept and mutate JWT / signed payloads |
| Observatory | https://github.com/mdn/mdn-http-observatory | SRI presence check on external script tags |
| Wfuzz | https://github.com/xmendez/wfuzz | Forge `alg:none` JWTs and observe acceptance |
