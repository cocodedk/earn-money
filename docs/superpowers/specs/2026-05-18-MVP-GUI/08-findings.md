# 8. Findings

## 8.1 Findings list page

Route:

```text
/findings
```

Purpose: list all findings.

Filters:

```text
project
target
scan run
stub
severity
confidence
status
```

Table columns:

```text
Title
Target
Stub
Category
Severity
Confidence
Status
Created at
Actions
```

Actions:

```text
Open finding
Open evidence
```

## 8.2 Finding detail page

Route:

```text
/findings/:findingId
```

Purpose: show one finding.

Show:

```text
title
target
scan run
stub
category
severity
confidence
status
data JSON
linked evidence
created at
updated at
```

Linked evidence table:

```text
source
url
field
matched value
raw excerpt
created at
```
