# Operator playbook

How the operator drives the earning loop day-to-day. Skim before each session. Read in full once.

This file documents the *human-gated* parts of the pipeline. The automated parts (passive recon, scope sync, active scans on schedule) just run; the operator's job is the bits a runner can't do.

## Daily session structure (target: 30-60 min)

```
   recon  →  triage  →  verify  →  draft  →  edit  →  submit
   ────       ────       ────       ────       ────       ────
   cron       bin/       human      bin/       human      bin/
   (auto)     triage     (you)      draft      (you)      submit
```

1. **Pull the queue.** SSH to the VPS, check what triage produced overnight:
   ```bash
   ssh recon-vps
   cd /opt/earn-money
   ls -la findings/_queue/
   ```
   Empty queue means no new signals reached the triage threshold (or nothing was scanned). That's a normal day.

2. **Read each queue entry.** Open `findings/_queue/<hash>.md`. The frontmatter has the metadata; the body has the scanner's hit and a checklist of things to verify manually.

3. **Reproduce.** Caido is fine. The CLAUDE.md rule: one redacted screenshot, then stop. No PII exfiltration even when permitted.

4. **Promote what reproduces (first human gate).** Transition state in the DB:
   ```bash
   .venv/bin/python -c "
   from pathlib import Path
   from earn_money import config, db
   from earn_money._time import now_iso
   from earn_money.triage import history
   paths = config.Paths.from_root(Path('/opt/earn-money'))
   conn = db.open_db(paths.program_db('hackerone', 'security'))
   history.transition_state(
       conn, finding_hash='<full-hash>', to_state='verified',
       actor='operator', note='reproduced; impact: <one sentence>',
       now=now_iso(),
   )
   "
   ```

5. **Draft the report.**
   ```bash
   bin/draft --program <slug> --hash <hash>
   ```
   Opens nothing — it writes `reports/drafts/<hash>.md`. Open that in your editor.

6. **Substantive rewrite.** The template is a starting draft, not a finished product. Replace every `[Operator: ...]` cue. Write in your voice. Reports that read as scanner-output get downgraded by HackerOne triage.

7. **Delete the scanner-evidence block** before filing. The template has a visible "DELETE BEFORE FILING" warning. It's there because forgetting is easy.

8. **File on the platform.** Paste into HackerOne. Note the platform's assigned report ID.

9. **Mark submitted (second human gate).**
   ```bash
   bin/submit --program <slug> --hash <hash> \
       --report-id H1-XXXXXXX \
       --note "Filed at <time>; primary impact <X>"
   ```
   This records the external_report_id and transitions verified → submitted.

## When the freeze flag fires

A scope-sync run detected a destructive scope diff (asset moved out of scope, scope shrunk). All recon halts for that program until you acknowledge.

```bash
ssh recon-vps
cd /opt/earn-money
ls programs/<platform>/<slug>/FROZEN      # confirm the flag is real
bin/ack-freeze <platform>/<slug>          # pops $EDITOR for the reason
```

`bin/ack-freeze` pops `$EDITOR` git-commit-style, asks for a reason, appends an audit row to `programs/<platform>/<slug>/freeze-acks.log`, then removes the FROZEN file. Empty reasons are rejected.

The freeze-acks.log is the *only* place this gets recorded. Don't `rm FROZEN` manually — you'd lose the audit trail.

## When you want to stop everything

```bash
rm /opt/earn-money/RECON_ENABLED
```

The kill-switch is checked every 5 seconds by every running scan. Removing the file halts the pipeline within ~10 seconds. Re-arm later with `touch RECON_ENABLED`.

## Triage rules of thumb

- **Info severity from nuclei** — `cookies-without-httponly`, `csp-script-src-wildcard`, `missing-cookie-samesite-strict` etc. — almost always `resolved_na`. Modern apps deliberately use these patterns:
  - `XSRF-TOKEN` lacks HttpOnly because it has to be JS-readable for the double-submit-cookie CSRF pattern.
  - `samesite=lax` (not strict) is OWASP-recommended for session cookies — strict breaks email-link flows.
  - CSP wildcards on `*.segment.com`, `*.googleapis.com` are intentional service allowlists.
- **CVE template hits** — verify the version-sniff actually maps to a vulnerable build. Many CVE templates are header-based and miss backports.
- **Dupes** — mark `resolved_dupe` after platform confirms. Track in `ops/ledger.md`.
- **Empty-IP assets from passive recon** — usually CNAMEs to dormant CloudFront distributions or NXDOMAINs. The pipeline correctly skips them. No action needed.

## VPS hygiene

- The dedicated VPS egress IP (`178.105.140.53`) is used for nothing else. No SSH-from-laptop traffic to anywhere via this VPS. No personal services. Triage teams cross-reference IPs.
- The `.env` lives only on the VPS and the laptop, never in git. Check `git status` before every commit.
- Raw recon outputs (`recon/outputs/`) are gitignored. They contain target URLs, scanner internals, and potential PII. Never copy elsewhere.

## Coordinated disclosure

- 90-day silence default before any public writeup.
- Program-specific terms override — read each program's policy page.
- One handle per platform; no sock-puppets, no multi-account.
- No social engineering, no DoS, no destructive payloads even where the program technically permits them.
