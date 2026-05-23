# OSS Tool Mapping — Phase 09: Path Traversal and File Inclusion

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

### 9.01 — Local File Read

**Detects:** Parameters that read arbitrary local files via path traversal sequences

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40017 (Path Traversal); tests `../` sequences |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module path_traversal`; fuzzes file params |
| Nuclei | https://github.com/projectdiscovery/nuclei | `file/lfi/` template pack; `/etc/passwd` canary |
| LFIscanner | https://github.com/R3LI4NT/LFIscanner | Dedicated LFI param fuzzer |
| YA-LFI | https://github.com/0x-Apollyon/YA-LFI | Broad LFI payload list, URL encoding variants |
| Wfuzz | https://github.com/xmendez/wfuzz | Payload fuzzing for path param values |

### 9.02 — Directory Traversal

**Detects:** `../` sequences and encoded variants escaping the document root

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Path-traversal active scanner; detects `../` and `..%2F` |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz path segments with traversal wordlists |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive brute-force reveals traversal-reachable paths |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Path traversal module handles double-encoding |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/files/` templates for common traversal patterns |

### 9.03 — Unsafe Download Endpoints

**Detects:** Download endpoints that accept user-controlled filenames/paths

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan on `file=`, `download=`, `path=` params |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz `filename` / `path` params with traversal + absolute paths |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates targeting `/download?file=` patterns |
| Ffuf | https://github.com/ffuf/ffuf | Content-discovery to enumerate download endpoint variants |
| arjun | https://github.com/s0md3v/Arjun | Discover hidden `file`, `path`, `src` parameters |

### 9.04 — Template File Include Bugs

**Detects:** Server-side template engines including attacker-controlled file paths

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | SSTI + LFI active rules together surface include paths |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Path traversal module reaches template include params |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssti/` templates; LFI templates for include-style params |
| LFIscanner | https://github.com/R3LI4NT/LFIscanner | Fuzzes include/template params directly |
| Wfuzz | https://github.com/xmendez/wfuzz | Payload lists for PHP/Jinja2/Twig include variants |

### 9.05 — Static File Bypass

**Detects:** Bypasses to static file serving rules that expose non-public files

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Fuzz URL paths with bypass wordlists (`..;/`, `%2f`, case variants) |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive enum with extension and case permutations |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/` + `misconfiguration/` templates for path bypass |
| Nikto | https://github.com/sullo/nikto | Checks common server path-bypass patterns |
| ZAP | https://github.com/zaproxy/zaproxy | Forced-browse and path normalisation checks |

### 9.06 — Archive Extraction Traversal

**Detects:** Zip Slip / tar traversal — archive entries writing outside the target dir

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Upload fuzzing with crafted archives via active scan |
| Nuclei | https://github.com/projectdiscovery/nuclei | `file/zip-slip` templates for upload endpoints |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz upload endpoints with malicious archive payloads |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and replace archive content in transit |

### 9.07 — Log File Exposure

**Detects:** Publicly reachable log files containing sensitive runtime data

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/logs/` template pack — `access.log`, `error.log`, etc. |
| Nikto | https://github.com/sullo/nikto | Checks 100+ known log paths by default |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz `/logs/`, `/log/`, `*.log` with dedicated wordlists |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive discovery of `.log` extension files |
| dirsearch | https://github.com/maurosoria/dirsearch | Built-in log-path wordlist |
| Gobuster | https://github.com/OJ/gobuster | Extension-mode (`-x log`) for log file discovery |

### 9.08 — Source Code Exposure

**Detects:** Source files, backups, and VCS artefacts reachable via HTTP

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/files/` — `.git`, `.env`, `*.bak`, `*.php~` |
| Nikto | https://github.com/sullo/nikto | Checks `.git/HEAD`, backup extensions, editor swap files |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz with `SecLists/Discovery/Web-Content/raft-*` wordlists |
| dirsearch | https://github.com/maurosoria/dirsearch | Extension permutations (`.bak`, `.old`, `.orig`) |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive enum surfaces nested source leaks |
| Gobuster | https://github.com/OJ/gobuster | Dir mode with backup-extension wordlist |
