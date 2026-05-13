# Tooling expansion — Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans`. Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** Bring the VPS toolkit to parity with the laptop + the spec's
section 8 + the operator's "everything we need" ask (scope C). One
idempotent extension to `scripts/install-vps.sh`. No new runners.

**Architecture:** Five labeled install blocks added in order to the
existing script. Each block: pre-check (skip if installed), download
or apt install, sanity-print of version. Re-runnable safely.

**Tech stack:** sh, apt-get, curl, go install (for tools that lack a
prebuilt release), git clone (wordlists). 200-line cap on
`install-vps.sh`; split into `scripts/install/*.sh` helpers if crossed.

## Task layout

Each task is a labeled block in `scripts/install-vps.sh`. One commit
per task. CodeRabbit after each.

- [ ] **T1. Extend ProjectDiscovery loop** to include `katana`, `naabu`.
  Same GH-release pattern already used for subfinder/httpx/nuclei. Two
  more iterations in the existing `for tool in ...` loop.

- [ ] **T2. Non-PD Go tools.** Install `amass` (v4), `gau`, `dalfox`,
  `gitleaks`, `trufflehog` via `go install <import-path>@latest` if
  `go` is on PATH; else fall back to `apt-get install` where the apt
  package exists (gitleaks/trufflehog do). Pre-check via `command -v`.
  Add a `go` install fallback (`apt install golang-go`) gated on
  whether any of the five are missing.

- [ ] **T3. Apt packages.** `apt-get install -y -qq nmap sqlmap ffuf`.
  One line. Idempotent by apt.

- [ ] **T4. rustscan.** Fetch the .deb from
  `github.com/RustScan/RustScan/releases/latest`, `dpkg -i`. Skip if
  `command -v rustscan` succeeds. Avoid cargo (would drag in the full
  Rust toolchain ~1.5 GB).

- [ ] **T5. Wordlists.** Shallow git clone of `danielmiessler/SecLists`
  to `/opt/seclists` (~1 GB shallow). Curl two assetnote files
  (`subdomains-top1million-5000.txt`, `parameters-top1million.txt`) to
  `/opt/assetnote/`. Skip if dirs already exist.

- [ ] **T6. Verify + document.** Add a final `log "installed
  versions:"` block that prints `--version` for every new tool. Update
  `README.md`'s external-tools section to note the new tools are on
  PATH (or under `/opt/`). Update the parent design spec's section 8
  if accurate.

## Cap check

After T5, `wc -l scripts/install-vps.sh`. If > 200, extract the largest
block into `scripts/install/<name>.sh` and source it from the
orchestrator. Most likely candidate: T2 (Go tools, the longest block).

## Verify per task

- **Lint:** the project's pre-commit hook runs `make smoke`. Even
  though install-vps.sh isn't covered by Python tests, the rsync-to-VPS
  flow doesn't break.
- **Functional:** `ssh recon-vps "bash /opt/earn-money/scripts/install-vps.sh"`
  after rsync. Verify the new tool appears on PATH via `command -v`.
- **Idempotency:** re-run the script. Each block should report "already
  present, skipping" and exit 0.

## Anti-goals

- No new recon runners.
- No nuclei template-set expansion (separate work).
- No per-program policy-tier gating for port scanners (separate work
  when we actually wire a runner).
