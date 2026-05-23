# OSS Tool Mapping — Phase 08: File Upload and File Handling

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

### 8.01 — Executable Upload

**Detects:** Upload endpoint accepts and serves executable binaries (.exe, .elf, .sh, etc.)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | Primary file-upload fuzzer; tests multiple content types |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40041 (File Upload add-on) covers unrestricted upload detection |
| Nuclei | https://github.com/projectdiscovery/nuclei | `file-upload` and `rce-via-upload` templates |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module upload` module |

### 8.02 — Script Upload

**Detects:** Upload endpoint accepts server-side scripts (.php, .jsp, .aspx, .py, etc.)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | Tests script extensions with content-type bypass |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan checks for web shell upload |
| Nuclei | https://github.com/projectdiscovery/nuclei | `webshell-upload` and `rce-via-upload` templates |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz file extension in multipart upload requests |

### 8.03 — SVG with Script

**Detects:** SVG upload with embedded event handlers or script elements stored and served

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | SVG upload with XSS payload in content |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for SVG XSS (rule 40012/40016) |
| Playwright | https://github.com/microsoft/playwright | Fetch and render uploaded SVG; confirm script execution |
| Nuclei | https://github.com/projectdiscovery/nuclei | `svg-xss-upload` templates |

### 8.04 — HTML Upload

**Detects:** Upload endpoint accepts .html/.htm files that can be served and rendered

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | HTML file upload bypass tests |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan detects HTML served from upload path |
| Nuclei | https://github.com/projectdiscovery/nuclei | `html-upload-xss` templates |

### 8.05 — MIME Mismatch

**Detects:** Server trusts Content-Type header without validating actual file content

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | Sends mismatched MIME type with malicious content |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and mutate Content-Type on upload request |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with content-type manipulation |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz Content-Type header in multipart requests |

### 8.06 — Extension Tricks

**Detects:** Bypass via double extension (.php.jpg), null byte, or case variation (.PHP)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | Built-in extension-trick wordlist |
| Ffuf | https://github.com/ffuf/ffuf | Custom wordlist with double/mixed extension variants |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with extension fuzzing payloads |
| Wfuzz | https://github.com/xmendez/wfuzz | Extension bypass wordlists in multipart data |

### 8.07 — Polyglot Files

**Detects:** Files valid as two formats simultaneously (e.g. JPEG+PHP, PDF+HTML)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | Polyglot payload generation and upload |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom polyglot upload templates |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Inject crafted polyglot body into upload request |

### 8.08 — Public Upload Paths

**Detects:** Uploaded files stored at predictable/publicly accessible URLs

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Brute-force upload directory paths |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive content discovery on upload base path |
| Gobuster | https://github.com/OJ/gobuster | Dir-mode scan against known upload directories |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-upload-directory` templates |
| Nikto | https://github.com/sullo/nikto | Identifies common upload path exposure |

### 8.09 — Predictable Filenames

**Detects:** Uploaded files stored with sequential, timestamp, or UUID-based names guessable by attacker

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Enumerate upload filenames with numeric/timestamp wordlists |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive scan with pattern-based wordlists |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates for sequential filename probing |

### 8.10 — Overwrite Attacks

**Detects:** Upload allows overwriting existing files (index files, config, other user files)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | Upload with known existing filename |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Replay upload requests with targeted filenames |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz filename parameter in upload form |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan for overwrite behaviour |

### 8.11 — Parser Crashes

**Detects:** Malformed files causing server errors, crashes, or DoS in image/document parsers

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Wfuzz | https://github.com/xmendez/wfuzz | Upload truncated/malformed file variants |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with malformed file payloads |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz upload with zero-byte, oversized, and corrupt files |
| Nuclei | https://github.com/projectdiscovery/nuclei | `dos-via-upload` templates for known parser bugs |

### 8.12 — Metadata Leakage

**Detects:** Uploaded files retained with EXIF/metadata; metadata exposed or location data leaked

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exif-metadata` / `metadata-disclosure` templates |
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan downloads and inspects file metadata |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept download responses; inspect binary metadata |

### 8.13 — Decompression Bombs

**Detects:** ZIP/tar archives that expand to enormous sizes causing memory/disk exhaustion

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan with zip-bomb payloads |
| Wfuzz | https://github.com/xmendez/wfuzz | Upload crafted archive with extreme compression ratio |
| Nuclei | https://github.com/projectdiscovery/nuclei | `zip-bomb` upload templates |

### 8.14 — Path Traversal in Upload Name

**Detects:** Filename parameter contains `../` sequences that write files outside upload dir

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 6 (path traversal) applied to filename param |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz filename with traversal sequences and encoding variants |
| Nuclei | https://github.com/projectdiscovery/nuclei | `path-traversal-upload` templates |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module upload` with traversal payloads |

### 8.15 — Arbitrary File Write

**Detects:** Upload chains leading to writing attacker-controlled content to arbitrary filesystem paths

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `arbitrary-file-write` and `rce-via-upload` templates |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan combining path traversal + upload vectors |
| Commix | https://github.com/commixproject/commix | Confirm file-write primitives lead to command execution |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Craft and replay upload requests with traversal filenames |
