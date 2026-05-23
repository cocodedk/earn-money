# OSS Tool Mapping — Phase 21: Infrastructure and Deployment Exposure

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

### 21.01 — Exposed Admin Panels

**Detects:** Publicly reachable admin/management UIs without authentication gates.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Gobuster | https://github.com/OJ/gobuster | Bruteforces common admin paths (/admin, /manager, etc.) |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive discovery of admin endpoints |
| dirsearch | https://github.com/maurosoria/dirsearch | Wordlist-based path scanner with admin-focused lists |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for common admin panel fingerprints |
| Nikto | https://github.com/sullo/nikto | Detects known admin paths and management interfaces |

### 21.02 — Debug Ports

**Detects:** Exposed debug/diagnostic ports (Java JDWP, Python debugpy, Node inspector, etc.).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for debug port banners and responses |
| Tsunami | https://github.com/google/tsunami-security-scanner | Plugin for JDWP/debug service detection |
| httpx | https://github.com/projectdiscovery/httpx | Probes non-standard ports for HTTP debug endpoints |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for debug header/endpoint leakage |

### 21.03 — Staging Environment Indexed

**Detects:** Staging/dev environments publicly reachable and indexed by search engines.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates checking robots.txt, sitemap, and staging hostnames |
| httpx | https://github.com/projectdiscovery/httpx | Probes staging/dev subdomains for live responses |
| Gobuster | https://github.com/OJ/gobuster | DNS mode to enumerate staging subdomains |
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan for staging indicators in responses |

### 21.04 — Default Credentials

**Detects:** Services still running with vendor-default usernames and passwords.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Large template set for default-credential login attempts |
| Nikto | https://github.com/sullo/nikto | Checks known default credential paths |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for authentication bypass via defaults |
| Tsunami | https://github.com/google/tsunami-security-scanner | Plugin detects default creds on common infra services |

### 21.05 — Misconfigured Reverse Proxy

**Detects:** Reverse proxy misconfigs that expose internal routes, bypass auth, or leak headers.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for path traversal and header manipulation |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for proxy header injection and bypass |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Inspect/modify proxy header handling |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz proxy routing rules and path normalization |
| Wapiti | https://github.com/wapiti-scanner/wapiti | DAST module for header and redirect misconfigs |

### 21.06 — Directory Listing

**Detects:** Web server directory listing enabled, exposing file trees.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nikto | https://github.com/sullo/nikto | Built-in check for directory listing responses |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule flags directory listing in responses |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates matching directory index HTML patterns |
| dirsearch | https://github.com/maurosoria/dirsearch | Discovers directories; response analysis flags listing |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Module checks for open directory listing |

### 21.07 — Cloud Bucket Exposure

**Detects:** Publicly readable or writable S3/GCS/Azure Blob storage buckets.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for bucket URL patterns and public-read checks |
| truffleHog | https://github.com/trufflesecurity/trufflehog | Scans bucket contents for secrets if public |
| ZAP | https://github.com/zaproxy/zaproxy | Passive detection of bucket URLs in responses |
| httpx | https://github.com/projectdiscovery/httpx | Probes discovered bucket URLs for public access |

### 21.08 — Container Metadata Leaks

**Detects:** Exposed container/cloud metadata endpoints (AWS IMDS, GCP metadata, Docker socket).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for 169.254.169.254 and metadata endpoint patterns |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan probing SSRF paths to metadata endpoints |
| httpx | https://github.com/projectdiscovery/httpx | Direct probe of known metadata URLs |
| Wapiti | https://github.com/wapiti-scanner/wapiti | SSRF module can reach metadata endpoints via app |

### 21.09 — CI/CD Artifact Exposure

**Detects:** Build artifacts, pipeline configs, or secrets exposed via CI/CD systems.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| truffleHog | https://github.com/trufflesecurity/trufflehog | Scans exposed artifact files for secrets |
| gitleaks | https://github.com/gitleaks/gitleaks | Detects hardcoded secrets in exposed config files |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for .env, .gitlab-ci.yml, Jenkinsfile exposure |
| Gobuster | https://github.com/OJ/gobuster | Discovers exposed build directories and artifact paths |
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan flags sensitive file extensions in responses |
