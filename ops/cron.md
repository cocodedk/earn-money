# Cron / scheduler

Documents what automated jobs are scheduled, where, and how to manage them.

## Status

No jobs scheduled yet. Phase 5 pipeline pending systemd timer setup.

## Planned schedule (per design spec)

| Schedule | Job | Location |
|----------|-----|----------|
| Daily | Scope sync (hackerone/security) | VPS systemd timer |
| Daily | Passive recon: subfinder + httpx | VPS systemd timer |
| Weekly | nuclei scan pass | VPS systemd timer |
| Daily 08:00 | Digest generation | VPS systemd timer |

## Setup

Install timers on the VPS:
```bash
./scripts/install-vps.sh
```

Then verify:
```bash
systemctl --user list-timers
```
