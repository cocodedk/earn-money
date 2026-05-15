# earn-money — design

**Date:** 2026-05-12
**Owner:** Babak Bandpey (cocode.dk)
**Status:** Draft — pending sign-off before implementation plan

## 1. Purpose

A continuous bug-bounty operation that converts existing tooling (`clawpwn`, `advisor-hierarchy`) and the operator's senior cybersecurity expertise into recurring online income with minimal per-revenue-unit human time.

Phase 2, deferred and conditional, is "FITS Express" — a self-serve mini-audit productizing FITS + clawpwn at €99–€499 per buyer. Phase 2 is documented but out of scope for the initial build.

Money lands in the existing cocode.dk business account under a `bug-bounty` revenue category to keep accounting consolidated.

## 2. Division of labor

The single most important architectural commitment: Claude (on cron) runs continuous recon, triages signals, hypothesizes vulnerabilities, drafts reports. Babak verifies findings, runs the explicit `submit` command, and replies to triage. **No finding crosses from `_queue/` to `_verified/` without Babak. No finding moves from `_verified/` to `_submitted/` without an explicit named command Babak runs.** Two human gates. Both are non-negotiable.

This division is what keeps the operation compliant with platform Terms of Service (HackerOne, Intigriti, YesWeHack all explicitly require human verification before submission) and what protects the handle from AI-slop reputation damage.

## 3. Identity, accounts, and operational security

### Phase 0 (Babak, one-time)

- HackerOne, Intigriti, YesWeHack accounts as cocode.dk sole proprietor. KYC: passport, Danish tax forms (W-8BEN for HackerOne).
- Payouts wired to the existing cocode.dk business account. Bookkeeping category: `bug-bounty`.
- Researcher handle separate from the cocode.dk brand. Recommended: a neutral identifier not cross-linked to consulting work in public — this firewalls reputation risk in either direction.
- One dedicated VPS with a static egress IP. **That IP is `178.105.140.53` (IPv4) and is used for nothing else** — no SSH from laptop, no other services, no personal traffic. Triage teams cross-reference IPs.
- **No IPv6 egress.** Decision recorded 2026-05-15. Hetzner provisions a v6 /64 by default; the netplan stanza on `eth0` removes the static v6 address, sets `dhcp6: false` + `accept-ra: false` + `link-local: []` so the route can't return via SLAAC/RA, and pins DNS to v4 resolvers (`1.1.1.1` + `9.9.9.9`). Rationale: dual-stack lets Go-based scanners (subfinder/httpx/nuclei/katana, bundled resolvers) silently pick v6 for AAAA-bearing targets, leaking a second source IP into triagers' logs and breaking the "one IP, one identity" invariant above.
- Dedicated DNS resolver on the VPS (1.1.1.1 or self-hosted). Not the ISP's resolver — avoids leaking enumeration patterns.
- Caido license (replaces Burp Pro at this stage — cheaper, sufficient for pipeline use).
- Tooling budget: ~€500/yr — Project Discovery Chaos API, Shodan, Caido. Add Burp Pro later only if manual testing volume grows.
- Accountant ping: confirm Danish tax/VAT treatment for foreign-platform payouts before first payout lands.

### Operational security rules

- `recon/outputs/` and `identity/platforms.md` are in `.gitignore` and never pushed to any remote.
- Raw recon artifacts may contain target PII or tokens — kept local or in encrypted storage only.
- One handle per platform. No sock-puppet accounts.

## 4. Repository layout

State is markdown-and-SQLite, both in the local working copy. Markdown is the human-readable surface; SQLite is the source of truth for assets and findings.

```
earn-money/
├── CLAUDE.md                    # hard rules: scope discipline, two gates, no auto-submit
├── README.md
├── .gitignore                   # recon/outputs/, identity/platforms.md, *.sqlite
├── identity/
│   └── platforms.md             # platforms, handle, payout config, VPS IP (gitignored)
├── programs/
│   └── <platform>/<slug>/
│       ├── scope.md             # in-scope, OOS, policy tier, scope_hash, last_synced
│       ├── notes.md             # judgment calls, ToS clarifications, target intuition
│       └── db.sqlite            # per-program assets + findings tables (gitignored)
├── recon/
│   ├── runners/                 # clawpwn-orchestrated pipelines per asset class
│   ├── wordlists/               # SecLists + assetnote (committed; small)
│   └── outputs/<date>/<program>/ # raw artifacts (gitignored)
├── findings/
│   ├── _queue/                  # candidates awaiting Babak's verify (gate 1)
│   ├── _verified/               # confirmed, awaiting explicit submit (gate 2)
│   ├── _submitted/<id>.md       # status tracking after submission
│   ├── _resolved/{paid,dupe,na,info}/
│   └── _archive/                # >90 days old
├── reports/
│   ├── templates/               # per vuln class (IDOR, SSRF, auth, etc.)
│   └── drafts/                  # platform-ready drafts before Babak sends
├── ops/
│   ├── cron.md                  # what's scheduled, where
│   ├── daily-digest.md          # overwritten daily at 08:00 local
│   ├── weekly-review.md         # overwritten Sunday
│   ├── ledger.md                # earnings, dates, programs
│   └── retro/<YYYY-MM>.md       # monthly retrospective
├── bin/
│   ├── submit                   # named CLI for gate 2 (verified → submitted)
│   └── ...                      # other operator-facing commands
└── docs/
    └── superpowers/
        └── specs/2026-05-12-earn-money-design.md   # this file
```

### Unit boundaries

1. **Program registry** (`programs/`) — single source of truth on scope. Every other unit reads from here. Nothing scans an asset not listed here.
2. **Recon runners** (`recon/runners/`) — clawpwn wrappers, one per asset class (web, API, mobile, cloud). Inputs: scope. Outputs: rows in the per-program SQLite + raw files in `recon/outputs/`.
3. **Triage / hypothesis engine** — reads SQLite + raw outputs, deduplicates against prior findings (O(1) via hash), generates candidates into `findings/_queue/`. Cannot advance past gate 1 autonomously.
4. **Report drafter** — for each item Babak promotes to `_verified/`, produces a platform-ready draft in `reports/drafts/`. Babak edits substantively and runs `bin/submit`.
5. **Ledger + retro** — updates `ops/ledger.md` on every state transition (queue → verified → submitted → resolved). Monthly retro auto-generated from the ledger.

### SQLite schema (per program)

`assets` — subdomain, IP, ports, fingerprint, first_seen, last_seen, in_scope_at_observation.
`findings` — finding_hash (vuln_class + target + signature), first_seen, current_state, notes_path.

Dedup is O(1) on finding_hash. The markdown `_queue/` files are views generated from the DB, not the source of truth.

## 5. Hard rules (CLAUDE.md)

These rules override anything else in the system, including operator convenience:

- Scope is gospel. No scan, no probe, no DNS lookup of an asset not in the current `scope.md` for that program.
- If scope sync fails or detects a destructive diff (asset moved out of scope), recon for that program freezes until Babak acks.
- No automated submission. Two human gates. `bin/submit` requires Babak typing it.
- Reports must read as human-expert-written. Substantive edit pass, not cosmetic.
- Rate-limited recon. Per-program caps. Default conservative; tune up only if program ToS explicitly permits.
- No social engineering, no DoS, no physical, no destructive payloads — even if a program technically allows them.
- No PII exfiltration. One redacted screenshot as proof-of-concept, then stop.
- One handle per platform. No sock-puppets.
- Coordinated disclosure. No public writeups until the program permits (default 90-day silence + program approval).
- `recon/outputs/`, `identity/platforms.md`, and `*.sqlite` are gitignored. Never pushed anywhere.

### Three-tier program policy

Every `scope.md` declares one `policy:` value:

- **`rate-limited-OK`** — automated scanning permitted. Full pipeline.
- **`manual-only`** — automated scanning prohibited. Babak scans by hand; Claude only maintains `scope.md`, tracks `findings/` state, and drafts reports from Babak's notes. **Recon runners refuse to start against any program with this flag.**
- **`ambiguous`** — ToS unclear. Written clarification requested from the program; the reply is saved in `programs/<slug>/notes.md`. Passive recon only (Chaos, Shodan, archive data — no live probing) until the program replies and the tier is promoted.

Rate is not the discriminator. Agent is. Slowing automated traffic does not convert a `manual-only` program into a `rate-limited-OK` program. That distinction is enforced by tier, not by request rate.

## 6. Scope discipline

- Every `scope.md` has `scope_hash` and `last_synced` fields.
- Hourly cron polls HackerOne / Intigriti scope APIs, diffs against `scope_hash`, updates `last_synced`.
- If sync detects a destructive diff (asset moved OOS), a freeze flag is written for that program. Recon refuses to run for that program until Babak removes the flag with an explicit command.
- Wildcard scopes (`*.example.com`) are resolved at scan-time, then each resolved asset is checked against an explicit OOS blocklist before the runner sends a single request.

## 7. Operational cadence

### Continuous (cron-driven, no human touch)

- **Scope sync** — hourly. Diff and freeze on destructive change.
- **Passive recon** — every 6h. Subdomain enumeration, DNS resolution, HTTP probing.
- **Change detection** — every 12h. New asset or new HTTP signature surfaces as a high-priority queue candidate.
- **Active recon** — daily, off-peak (UTC 02:00–05:00), rate-limited. Only runs if `RECON_ENABLED` exists and no per-program freeze flag is set.

### Daily

- **08:00 local — `ops/daily-digest.md` overwritten.** New assets, top 3–5 queue candidates, recon anomalies, scope diffs awaiting ack, triage replies awaiting response, ledger delta.
- Phone ping via chat-bus with the digest summary line.

### Babak's daily slot (30–60 min)

1. Read digest (5 min).
2. Ack scope diffs and freeze flags (≤5 min most days).
3. Verify top queue candidates in Caido. Bin into `_verified/`, `_resolved/dupe/`, or `_resolved/na/` (15–30 min).
4. For each `_verified/` item: read draft in `reports/drafts/`, edit substantively, run `bin/submit` (10–15 min per submission).
5. Reply to triage threads (5–15 min when applicable).

### Sunday weekly review (60–90 min)

- `ops/weekly-review.md` generated by Claude: per-program scorecard (assets monitored, candidates produced, false-positive rate, verification load, submissions, duplicates, paid, current €/hour-of-Babak's-time).
- Recommendations: kill / deprioritize / double-down per program. Babak signs off.
- Underperforming program = >2 weeks of recon with zero `_verified/` items → flagged for removal.

### Monthly (`ops/retro/<YYYY-MM>.md`)

- Ledger summary, payout reconciliation against bookkeeping.
- AI-slop audit: spot-check three random submitted reports for human-expert quality. If degrading, retrain templates before next month.
- Scope-selection retrospective: are we still targeting low-density programs, or drifting into Shopify-class noise?
- Private-program invitations received → ack and prioritize.

### Quarterly (Babak, with Claude's prep)

- Accountant check-in (post first payout).
- Tooling re-eval: is Caido still enough?
- Reputation milestone: are private invitations flowing? If not, why?

### SLAs

- Triage reply: ≤24h.
- Scope-diff ack: ≤4h after digest, else recon stays frozen for that program.
- Kill-switch: `RECON_ENABLED` is checked on every cron invocation, not just at boot. `rm RECON_ENABLED` stops the whole operation immediately.

## 8. Tooling

### Free, must-have

`subfinder`, `amass` (passive), `httpx`, `nuclei`, `gau`/`waymore`, `katana`, `ffuf`, `SecLists`, `assetnote` wordlists.

### Paid, worth it

- **Chaos API** (Project Discovery) — passive subdomain data.
- **Shodan** — initial asset discovery and ongoing monitoring.
- **Caido** — proxy/intercept tool for the pipeline and for Babak's manual verification. Cheaper than Burp Pro and sufficient at this stage.

### Skip

- Burp Pro (until manual volume justifies it).
- Paid wordlists beyond SecLists + assetnote.

## 9. Phasing

> **🪓 Five-step cut on 2026-05-12.** A first-principles pass (both reviewers agreed 100%) shrank the remaining roadmap. The original phasing below is preserved for context, but the *actual* go-forward plan is in [`../decisions/2026-05-12-five-step-cut.md`](../decisions/2026-05-12-five-step-cut.md). Summary:
> - **Phase 3a/3b**: shipped as planned.
> - **Phase 3c (katana + ffuf scheduled)**: 🅿️ parked. Manual ffuf only, on demand.
> - **Phase 3d (digest, phone-ping, timer chain, full ack-freeze)**: 🅿️ mostly parked. Only a tiny `bin/ack-freeze` shell helper survives.
> - **Phase 4**: 🟢 next. Shrunk to `bin/submit` + `bin/draft` + a report template — prove one earning loop.
> - **Phase 5**: 🟡 measure-not-build. Month-3 €500/mo gate stays.
> - **Phase 6**: ❌ dropped from active scope. Conditional future, not next-up.

**Phase 0 — Accounts.** Babak, half a day total. KYC, VPS, payout wiring, accountant ping.

**Phase 1 — Foundation.** Claude, 3–5 days. Repo skeleton, `CLAUDE.md`, SQLite schema, HackerOne scope-sync runner, one program fully onboarded with `scope.md` and `policy:` set, `RECON_ENABLED` and freeze flags wired into every runner.

**Phase 2 — First recon runner.** Claude, 2–3 days. End-to-end passive recon → SQLite → markdown queue view. One program only. Rate-limited. No active recon yet.

**Phase 3 — Active recon + daily digest.** Claude, 3–4 days. nuclei + katana + ffuf scheduled, 08:00 digest generation, phone ping. Triage engine produces first queue candidates.

**Phase 4 — First submission loop.** Babak + Claude, ~1 week. Babak verifies candidates, Claude drafts reports, Babak edits and submits. Goal: first submission landed. Pay/dupe/N/A doesn't matter — pipeline integrity does.

**Phase 5 — Reputation build.** Months 1–3. Scale slowly to additional programs only after the one-program pipeline is clean. Template refinement from triage feedback. Monthly retros. AI-slop self-audit. Decision gate at month 3: pipeline producing >€500/month *and* clean human-quality reports? Yes → continue. No → kill or pivot.

**Phase 6 — FITS Express (deferred).** Only if Phase 5 hits its month-3 bar. 2–3 weeks of work when triggered. Self-serve €99–€499 mini-audit, funnel from cocode.dk and the LinkedIn audience.

Phases 1–4 are sequential. Phase 5 is the reality-check gate. Phase 6 is conditional on Phase 5.

### Phase 4 program count: one

Pick a single program with the best fit (low researcher density, asset class Babak knows well) and run the whole pipeline against it. Calibrate on one before scaling. Slowest growth, lowest noise, cleanest learnings. New programs are added during Phase 5 once the pipeline has proven clean.

## 10. Realism

- **Month 1:** €0–€200. KYC, calibration, false-positive volume, target intuition.
- **Month 3:** median €200–€800. New handles are deprioritized in triage; that lifts after 3–6 months of clean submissions.
- **Tail:** occasional criticals dominate the distribution. Median per validated bug across the industry is €300–€1,500; criticals can be €5k–€50k. Most months earn nothing close to the mean.

### Most-likely failure modes

1. **Triage time eats verification time.** Volume from the pipeline competes with the deep manual work that actually closes findings. Mitigation: hard cap on queue items presented per day, plus Sunday review to kill programs producing only noise.
2. **Early aggressive scan triggers an IP ban before the handle has a reputation buffer.** No recovery. Mitigation: conservative default rate limits, scope-sync freeze on destructive diffs, `manual-only` programs run by Babak only.
3. **AI-slop reputation tag.** Claude-drafted reports flagged by triage teams. Mitigation: substantive human edit pass, monthly spot-audit, template retraining on triage feedback.
4. **Duplicate collisions on high-density programs.** Shopify-class targets have >60% duplicate rates. Mitigation: scope selection strategy favors low-density programs and asset classes with low researcher coverage (mobile, thick clients, niche B2B SaaS).
5. **Private-program access takes 3–6 months of reputation.** Public programs are the worst ROI. Bake the delay into expectations; it is not a project failure, it is a project phase.

## 11. Things explicitly out of scope

- The marketing operations for cocode.dk consulting (lives in `run-my-cocodedk-business/`). This project is autonomous online income, not consulting funnel work.
- FITS Express productization until Phase 5 gates it in.
- Any program with `policy: manual-only` from the automated pipeline. Babak runs those by hand; Claude only handles scope, state, and drafts.
- Audience-monetization plays (newsletter, sponsorships, affiliate). Rejected during brainstorming as too slow for the goal.
