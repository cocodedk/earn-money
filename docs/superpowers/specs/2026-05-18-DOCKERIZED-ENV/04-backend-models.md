# 4. Backend models

Create minimal models.

## Project

```text
id
name
description
created_at
updated_at
```

## ScanTarget

```text
id
project
base_url
host
ip
status
created_at
updated_at
```

Status values:

```text
active
retired
```

## ScanRun

```text
id
project
stub_slug
status
started_at
finished_at
created_at
updated_at
```

Status values:

```text
queued
running
paused
stopping
stopped
failed
done
```

## ScanTargetRun

```text
id
scan_run
target
status
started_at
finished_at
created_at
updated_at
```

Status values:

```text
queued
running
paused
stopping
stopped
failed
done
```

## ScanEvent

```text
id
scan_run
target nullable
level
event_type
message
data json
created_at
```

Levels:

```text
debug
info
warning
error
```

## Finding

```text
id
scan_run
target
stub_slug
title
category
severity
confidence
status
data json
created_at
updated_at
```

## Evidence

```text
id
scan_run
target
finding nullable
source
url
method
field
matched_value
raw_excerpt
content_hash
data json
created_at
```

Evidence should be append-only.

Do not silently rewrite evidence.
