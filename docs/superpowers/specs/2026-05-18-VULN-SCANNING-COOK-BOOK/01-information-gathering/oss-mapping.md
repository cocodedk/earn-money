# OSS Tool Mapping — Phase 01: Information Gathering

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
| hakrawler | https://github.com/hakluke/hakrawler | Fast passive crawl from JS/HTML/links |

## Stub Mappings

### 1.01 — Framework Detection

**Detects:** Technology/framework fingerprinting from HTTP responses and page content.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Wapiti | https://github.com/wapiti-scanner/wapiti | Fingerprinting module; reports framework |
| Nuclei | https://github.com/projectdiscovery/nuclei | `technologies/` templates fingerprint frameworks |
| Nikto | https://github.com/sullo/nikto | Server banner + framework clues |
| httpx | https://github.com/projectdiscovery/httpx | Tech detection via `-tech-detect` flag |

### 1.02 — Server Headers

**Detects:** Leaky `Server`, `X-Powered-By`, and other revealing response headers.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/` + `misconfiguration/` header templates |
| Nikto | https://github.com/sullo/nikto | Flags verbose server headers by default |
| httpx | https://github.com/projectdiscovery/httpx | `-include-response-header` for header harvesting |
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan rule: Information Disclosure via HTTP headers |

### 1.03 — Frontend Framework

**Detects:** JS framework leaks (React version, Angular metadata, Vue dev-mode).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Retire.js | https://github.com/RetireJS/retire.js | Identifies outdated JS libs including framework versions |
| Nuclei | https://github.com/projectdiscovery/nuclei | `technologies/` JS framework detection templates |
| httpx | https://github.com/projectdiscovery/httpx | `-tech-detect` infers frontend frameworks |

### 1.04 — Backend Hints

**Detects:** Backend stack indicators (error messages, runtime in headers, stack fingerprints).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nikto | https://github.com/sullo/nikto | Known backend fingerprint patterns |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/` backend identification templates |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rules for backend disclosure |

### 1.05 — Package Version Leaks

**Detects:** Disclosed library versions in headers, HTML comments, or `package.json`-like endpoints.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Retire.js | https://github.com/RetireJS/retire.js | Extracts and correlates JS package versions |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates matching version strings in responses |
| Nikto | https://github.com/sullo/nikto | Version disclosure checks |

### 1.06 — Hidden Routes

**Detects:** Non-linked routes and endpoints reachable via brute-force or wordlist.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive brute-force, status filtering |
| Ffuf | https://github.com/ffuf/ffuf | Fast fuzzing for hidden paths |
| Gobuster | https://github.com/OJ/gobuster | Dir/file brute-force |
| dirsearch | https://github.com/maurosoria/dirsearch | Path scanning with extensions |

### 1.07 — Backup Files

**Detects:** `.bak`, `.old`, `.orig`, `~` suffixed copies of source files.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Feroxbuster | https://github.com/epi052/feroxbuster | Extension-based wordlist scan |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz with backup extension wordlist |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/files/` backup file templates |
| Nikto | https://github.com/sullo/nikto | Built-in backup file checks |

### 1.08 — Exposed Admin Panels

**Detects:** Publicly accessible admin interfaces (`/admin`, `/phpmyadmin`, etc.).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-panels/` template collection |
| Feroxbuster | https://github.com/epi052/feroxbuster | Wordlist discovery of admin paths |
| Nikto | https://github.com/sullo/nikto | Checks common admin panel locations |

### 1.09 — Old Endpoints

**Detects:** Legacy versioned API paths (`/api/v1/`, `/old/`, `/legacy/`).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Version-path fuzzing |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive discovery uncovers versioned roots |
| ParamSpider | https://github.com/devanshbatham/ParamSpider | Mines archived URLs for old endpoints |

### 1.10 — Debug Pages

**Detects:** Debug/profiling endpoints (`/debug`, `/_debug`, `/metrics`, `/pprof`).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-panels/` + `misconfiguration/` debug templates |
| Feroxbuster | https://github.com/epi052/feroxbuster | Wordlist with debug path variants |
| Nikto | https://github.com/sullo/nikto | Checks common debug endpoints |

### 1.11 — Robots.txt

**Detects:** Sensitive paths disclosed in `robots.txt` `Disallow` directives.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/` robots.txt parse template |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: information in robots.txt |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Reads robots.txt as crawl seed |

### 1.12 — Sitemap XML

**Detects:** URL enumeration via `sitemap.xml` and nested sitemaps.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Katana | https://github.com/projectdiscovery/katana | Consumes sitemaps as seed input |
| ZAP | https://github.com/zaproxy/zaproxy | Spider consumes sitemap.xml |
| Nuclei | https://github.com/projectdiscovery/nuclei | Template confirms presence + extracts URLs |

### 1.13 — Security.txt

**Detects:** Presence/absence and quality of `/.well-known/security.txt`.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Template verifies security.txt fields |
| httpx | https://github.com/projectdiscovery/httpx | Simple probe for file existence |

### 1.14 — Source Maps

**Detects:** Exposed `.map` files leaking original JS/TS source code.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/files/` sourcemap templates |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz `.map` extension on known JS files |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: JavaScript source map disclosure |

### 1.15 — Public JavaScript Bundles

**Detects:** Unminified bundles or bundles containing secrets/internal routes.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Retire.js | https://github.com/RetireJS/retire.js | Scans bundles for known vulnerable libraries |
| truffleHog | https://github.com/trufflesecurity/trufflehog | Secret scanning inside JS bundle content |
| Katana | https://github.com/projectdiscovery/katana | Discovers bundle URLs for downstream analysis |

### 1.16 — Stack Traces

**Detects:** Full stack traces returned in error responses.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: stack trace disclosure |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Error-triggering requests surface traces |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/` stack trace detection templates |

### 1.17 — Verbose API Errors

**Detects:** API error responses containing internal paths, DB schema, or debug info.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rules for verbose error content |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Triggers errors via malformed inputs |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz parameters to elicit verbose errors |

### 1.18 — Framework Debug Pages

**Detects:** Framework-native debug pages (Django debug, Rails error pages, Laravel whoops).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Framework-specific debug page templates |
| Nikto | https://github.com/sullo/nikto | Known debug page URL patterns |
| ZAP | https://github.com/zaproxy/zaproxy | Passive detection of framework error pages |

### 1.19 — SQL/ORM Errors

**Detects:** Database error messages in responses (SQL syntax errors, ORM exceptions).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: SQL error disclosure |
| Wapiti | https://github.com/wapiti-scanner/wapiti | SQL error injection probe |
| Sqlmap | https://github.com/sqlmapproject/sqlmap | Detects and enumerates on SQL error leaks |

### 1.20 — .env Files

**Detects:** Exposed `.env` files leaking credentials and config secrets.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/files/env-file.yaml` template |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz common `.env` paths |
| Nikto | https://github.com/sullo/nikto | Checks `.env` and `*.env` exposure |

### 1.21 — Git Repository Exposure

**Detects:** Exposed `.git/` directory allowing source reconstruction.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/configs/git-config.yaml` + related |
| gitleaks | https://github.com/gitleaks/gitleaks | Scans reconstructed repo for secrets |
| Nikto | https://github.com/sullo/nikto | Checks `.git/HEAD` accessibility |
| Feroxbuster | https://github.com/epi052/feroxbuster | Discovers `.git/` sub-paths |

### 1.22 — Config Files

**Detects:** Exposed config files (`web.config`, `application.yml`, `settings.py`, etc.).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/configs/` template collection |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz config file paths + extensions |
| Nikto | https://github.com/sullo/nikto | Built-in config file exposure checks |

### 1.23 — Log Files

**Detects:** Publicly accessible log files (`error.log`, `access.log`, `debug.log`).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/logs/` templates |
| Feroxbuster | https://github.com/epi052/feroxbuster | Wordlist with log file patterns |
| Ffuf | https://github.com/ffuf/ffuf | Extension fuzzing for `.log` files |

### 1.24 — Backup Archives

**Detects:** Exposed `.zip`, `.tar.gz`, `.sql.gz` archives of application or DB.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/files/` archive templates |
| Feroxbuster | https://github.com/epi052/feroxbuster | Extension wordlist for archive types |
| Ffuf | https://github.com/ffuf/ffuf | Archive-extension fuzzing |

### 1.25 — Exported Database Files

**Detects:** Exposed `.sql`, `.dump`, `.sqlite`, `.db` files.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/files/` DB file templates |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz DB file extensions and common names |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive discovery with DB extension list |
