# 5. Scan runs

## 5.1 Create scan run page

Route:

```text
/scan-runs/new
```

Purpose: create a scan run.

Form fields:

```text
project
stub_slug
targets
```

Target selection:

```text
all active project targets
or selected targets only
```

Default:

```text
all active targets
```

Actions:

```text
Create scan run
Create and start scan run
Cancel
```

Validation:

```text
project is required
stub_slug is required
at least one target is required
```

## 5.2 Scan runs list page

Route:

```text
/scan-runs
```

Purpose: list all scan runs.

Table columns:

```text
ID short
Project
Stub
Status
Targets
Findings
Started at
Finished at
Actions
```

Status badges:

```text
queued
running
paused
stopping
stopped
failed
done
```

Actions:

```text
Open
Start
Pause
Resume
Stop
```

Only show valid actions.

Rules:

```text
queued -> Start
running -> Pause, Stop
paused -> Resume, Stop
stopping -> no action
stopped -> no action
failed -> no action
done -> no action
```
