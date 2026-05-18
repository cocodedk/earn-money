# Glossary

Acronyms from four overlapping disciplines: software engineering, web security, infrastructure, and bug-bounty practice. New collaborators (or future-you) start here.

## Engineering principles

| Term | Meaning |
|---|---|
| **TDD** | Test-Driven Development — write the failing test first, then the minimum code to pass, then refactor. Strict in this repo. |
| **DRY** | Don't Repeat Yourself — extract shared logic into named utilities; never copy-paste. |
| **SOLID** | Five OO design principles (Single-responsibility, Open-closed, Liskov-substitution, Interface-segregation, Dependency-inversion). Applied loosely: mostly the single-responsibility one. |
| **KISS** | Keep It Simple, Stupid — prefer the obvious solution over the clever one. |
| **YAGNI** | You Aren't Gonna Need It — don't build features that aren't yet required. |
| **DAO** | Data Access Object — a thin module that wraps SQL behind a typed Python API. `recon/runs.py`, `recon/services.py`, `recon/signals.py` are DAOs. |
| **CLI** | Command-Line Interface — the shell wrappers in `bin/` (`scope-sync`, `passive-recon`, `httpx-probe`, etc.). |
| **CI** | Continuous Integration — automated build + test on every commit. Pre-commit hook is the local equivalent here. |
| **PR** | Pull Request — GitHub's name for a proposed merge. |

## Pipeline / bug-bounty domain

| Term | Meaning |
|---|---|
| **Recon** | Reconnaissance — discovering targets and surface area on a program. *Passive* recon reads public data (CT logs, archives, Chaos). *Active* recon sends traffic to the target. |
| **Scope** | The set of assets a program authorizes us to test. Lives in `programs/<platform>/<slug>/scope.md`. Wildcards (`*.example.com`) and an out-of-scope deny list both apply. |
| **OOS** | Out-of-Scope — an asset the program forbids testing. Tools may surface OOS assets; the runner wrapper drops them before any DB write and counts them via `oos_drops`. |
| **Triage** | The step where raw signals from recon tools become candidate findings in `findings/_queue/`. Triage cannot promote past `_queue/`; that requires the operator. |
| **Finding** | A specific vulnerability candidate. Has a stable `finding_hash` (so the same finding seen twice doesn't create two rows) and a state-machine (`queued` → `verified` → `submitted` → `resolved_paid` / `resolved_dupe` / `resolved_na` / `resolved_info`). |
| **Program** | A bug-bounty target — a company or product that has a public (or invited) scope. `hackerone/security` is the example program currently in the registry. |
| **Platform** | The bug-bounty broker. HackerOne, Bugcrowd, Intigriti, etc. This repo currently only supports HackerOne. |
| **Bounty** | The money paid for a valid finding. Bounty range, payout history, and program reputation feed scope-selection decisions. |
| **N/A** | Not Applicable — a platform's reject reason for a finding (e.g., out of scope after the fact, no security impact). |
| **POC** | Proof of Concept — the minimal evidence demonstrating a vulnerability. Repo policy: one redacted screenshot, then stop. No PII exfil. |
| **SLA** | Service Level Agreement — the program's stated response time for triage replies. |

## Security / vulnerability classes

| Term | Meaning |
|---|---|
| **CVE** | Common Vulnerabilities and Exposures — the public catalog of known software vulnerabilities. `nuclei`'s `cves/` template directory tests for these. |
| **IDOR** | Insecure Direct Object Reference — accessing other users' data by incrementing an ID in a URL or request. High-paying finding class; not detected by scanners. |
| **SSRF** | Server-Side Request Forgery — tricking a server into fetching a URL of your choice (often pointing it at internal services). |
| **WAF** | Web Application Firewall — an inline filter sitting in front of a target. Often blocks recon traffic; runners must tolerate WAF responses without aborting. |
| **MFA** | Multi-Factor Authentication — the system you try to bypass when looking for authentication flaws. |
| **JWT** | JSON Web Token — a self-signed authentication token. Common source of bugs (signature verification skips, algorithm confusion). |
| **PII** | Personally Identifiable Information — names, emails, IDs, etc. Repo rule: never exfiltrate it, even when permitted. |
| **ToS** | Terms of Service — the program's rules. `ambiguous` policy programs are ones where the ToS is unclear; passive only until clarified. |
| **KYC** | Know Your Customer — identity verification (Phase 0 chore for bug-bounty platforms that pay out). |

## Tech stack

| Term | Meaning |
|---|---|
| **API** | Application Programming Interface — usually the HTTP endpoints a service exposes. |
| **CDN** | Content Delivery Network — geographically distributed cache (e.g. Cloudflare). Many in-scope assets sit behind CDNs. |
| **DNS** | Domain Name System — the protocol that resolves hostnames to IPs. Passive recon uses 1.1.1.1 / 9.9.9.9 as recursive resolvers. |
| **TLS** | Transport Layer Security — the encryption layer under HTTPS. `httpx` records a TLS summary per service. |
| **HTTPS** | HTTP Secure — HTTP over TLS. |
| **JSONL** | JSON Lines — one JSON object per newline-terminated line. The native output format for `httpx`, `nuclei`, `subfinder`, and others. |
| **TLD** | Top-Level Domain — `.com`, `.dk`, `.co.uk`. |
| **PSL** | Public Suffix List — Mozilla's curated list of effective TLDs, including private suffixes like `s3.us-west-2.amazonaws.com`. We use `tldextract` with `include_psl_private_domains=True` so a scoped S3 bucket FQDN isn't collapsed to `amazonaws.com`. |
| **IDN** | Internationalized Domain Name — non-ASCII hostnames. Normalization rules in the finding-hash spec call for `idna.encode(..., uts46=True)`. |
| **FQDN** | Fully Qualified Domain Name — a complete hostname like `api.example.com`, no trailing dot needed in our code. |
| **CT logs** | Certificate Transparency logs — public append-only logs of every issued TLS cert. A primary source for passive subdomain discovery. |
| **SQLite** | The embedded relational database. Each program has its own `db.sqlite` storing assets, services, runs, signals, and findings. Schema is versioned via `PRAGMA user_version`. |
| **SIGTERM / SIGKILL** | Unix process signals. The batch wrapper sends SIGTERM, waits 5 s, then SIGKILL when a subprocess must be stopped. |
| **UUID** | Universally Unique Identifier. `run_id` is a 32-char hex UUID4. |

## Tools

| Tool | Purpose |
|---|---|
| **subfinder** | ProjectDiscovery's passive subdomain enumerator. Queries CT logs, archive.org, Chaos, and ~30 other passive sources. Phase 2. |
| **Chaos** | ProjectDiscovery's curated subdomain dataset for public bug-bounty programs. Free API tier. Phase 2. |
| **httpx** | ProjectDiscovery's HTTP fingerprinter. Probes a list of hosts/URLs and records status, title, server, technologies, redirect target, TLS summary. Phase 3a. *Not* the Python httpx HTTP client library — different tool. |
| **nuclei** | ProjectDiscovery's template-based vulnerability scanner. Runs YAML-defined checks for CVEs and standard misconfigurations against live HTTP services. Phase 3b. |
| **katana** | ProjectDiscovery's crawler. Discovers endpoints, parameters, JS-referenced URLs from a starting set of HTTP roots. Phase 3c (parked). |
| **ffuf** | "Fuzz Faster U Fool" — a Go-based content / parameter / vhost fuzzer. Brute-forces hidden paths from wordlists. Phase 3c (parked). |
| **Caido** | Operator's proxy/intercept tool for manual verification. Cheaper than Burp Pro and sufficient at this stage. |
| **clawpwn** | The internal name for this whole pipeline's toolkit/runner abstraction. Some runner code may eventually move to a thin clawpwn wrapper. |
| **SecLists** | Daniel Miessler's curated wordlist collection. Used by `ffuf` for content discovery. |
| **assetnote** | Curated wordlists from Assetnote. Higher signal-to-noise than SecLists for modern web stacks. |
| **Shodan** | Search engine for internet-exposed services. Used for asset discovery and ongoing monitoring (Phase 5+). |

## Pipeline phases

| Phase | Sub-phases | What ships |
|---|---|---|
| **Phase 0** | Accounts | KYC, VPS provisioning, payout wiring. Operator-owned, not in code. |
| **Phase 1** | — | Foundation: scope-sync runner, kill-switch + freeze flags, SQLite schema. |
| **Phase 2** | — | Passive recon: `subfinder` + Chaos + DNS resolution → SQLite. |
| **Phase 3** | 3a / 3b / 3c / 3d | Active recon + daily digest. |
| **3a** | — | Active-recon foundation + `httpx` + migration framework + watchdog + batch wrapper. |
| **3b** | — | `nuclei` runner + triage engine v1 + expanded `findings` schema + state machine. |
| **3c** | — | `katana` crawler + `ffuf` fuzzer. Parked. |
| **3d** | — | 08:00 daily digest, phone ping, `bin/ack-freeze`, systemd timers. Mostly parked; only `bin/ack-freeze` survives. |
| **Phase 4** | — | First submission loop: operator verifies, drafts get edited, `bin/submit` fires. Shipped. |
| **Phase 5** | — | Reputation build: scale to more programs, monthly retros. Measure-not-build. |
| **Phase 6** | — | FITS Express (deferred): self-serve mini-audit product. Conditional on Phase 5 hitting its month-3 bar. Dropped from active roadmap. |

## Infrastructure

| Term | Meaning |
|---|---|
| **VPS** | Virtual Private Server — the dedicated cloud box that runs the cron/timer pipeline. The egress IP is used for nothing else. Operator SSH-in only; no traffic out beyond what runners produce. |
| **SSH** | Secure Shell — operator's connection to the VPS. |
| **systemd timers** | Replacement for cron used in Phase 3+. Per-timer timezone (`Timezone=Europe/Copenhagen` for the digest), `Persistent=true` to backfill missed runs after reboot, explicit `After=` ordering between dependent units. |
| **UTC** | Coordinated Universal Time — the default timezone for all recon runners. |
| **CET / CEST** | Central European Time / Central European Summer Time — operator's local timezone. Switches at DST boundaries; the daily digest is scheduled in `Europe/Copenhagen` so it always fires at 08:00 local. |
| **DST** | Daylight Saving Time — the spring/fall hour shift. Triage runs early enough in UTC that the digest fires safely after it in both CET and CEST. |
