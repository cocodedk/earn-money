# 6. Scan run detail page

Route:

```text
/scan-runs/:scanRunId
```

Purpose: control one scan and watch it run.

This is the most important MVP page.

## Header

Show:

```text
Scan run ID
Project
Stub
Status
Started at
Finished at
```

Buttons:

```text
Start
Pause
Resume
Stop
```

Only valid buttons should be enabled.

## Target status table

Columns:

```text
Target
Status
Started at
Finished at
Findings count
Evidence count
Actions
```

Actions:

```text
Open target result
Open findings
Open evidence
```

## Live events panel

Show live events from SSE.

Each event row:

```text
time
level
target
event_type
message
```

Levels:

```text
debug
info
warning
error
```

The newest event can appear at top or bottom. Pick one and keep it consistent.

Controls:

```text
Auto-scroll on/off
Clear local view
Reconnect
```

Do not delete backend events when clearing local view.

## Findings panel

Show findings for this scan.

Columns:

```text
Title
Target
Category
Severity
Confidence
Status
Created at
Actions
```

## Evidence panel

Show evidence for this scan.

Columns:

```text
Source
Target
URL
Method
Field
Matched value
Created at
Actions
```
