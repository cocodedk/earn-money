# MVP GUI spec: scanner dashboard

React dashboard for the scanner platform.

Keep it simple. No fancy design. The goal is control and visibility.

## What the user must be able to do

- create a project
- add targets
- select one stub
- create a scan run
- start, pause, resume, and stop the scan
- see live scan events
- see target status
- see findings
- see evidence

## Spec layout

| File | Scope |
|------|-------|
| [01-app-layout.md](01-app-layout.md) | App shell: sidebar, top bar, main area |
| [02-projects.md](02-projects.md) | Projects list and project detail |
| [03-targets.md](03-targets.md) | Targets page |
| [04-stubs.md](04-stubs.md) | Stubs page and stub detail |
| [05-scan-runs.md](05-scan-runs.md) | Create scan run + scan runs list |
| [06-scan-run-detail.md](06-scan-run-detail.md) | Scan run detail (most important page) |
| [07-target-result.md](07-target-result.md) | Target result page |
| [08-findings.md](08-findings.md) | Findings list and finding detail |
| [09-evidence.md](09-evidence.md) | Evidence list and evidence detail |
| [10-settings.md](10-settings.md) | Settings / status page |
| [11-api.md](11-api.md) | Backend API endpoints + locked conventions |
| [12-live-events.md](12-live-events.md) | SSE behaviour and event shape |
| [13-ui-states.md](13-ui-states.md) | Loading / empty / error / success |
| [14-styling.md](14-styling.md) | Plain styling rules and badge colours |
| [15-workflow-seed.md](15-workflow-seed.md) | End-to-end MVP path + seed data |
| [16-acceptance.md](16-acceptance.md) | Acceptance criteria |
| [17-not-yet.md](17-not-yet.md) | Explicitly out of MVP scope |
| [18-design-tokens.md](18-design-tokens.md) | Typography, colour, spacing, layout dimensions |
| [19-component-primitives.md](19-component-primitives.md) | Shared component inventory + folder convention |
| [20-state-patterns.md](20-state-patterns.md) | Loading / empty / error / validation patterns |
| [21-current-project.md](21-current-project.md) | Frontend-only current-project storage contract |
