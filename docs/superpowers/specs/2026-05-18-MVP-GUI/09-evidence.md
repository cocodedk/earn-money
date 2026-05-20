# 9. Evidence

## 9.1 Evidence list page

Route:

```text
/evidence
```

Purpose: list evidence records.

Filters:

```text
project
target
scan run
finding
source
```

Table columns:

```text
Target
Source
URL
Method
Field
Matched value
Created at
Actions
```

Action:

```text
Open evidence
```

## 9.2 Evidence detail page

Route:

```text
/evidence/:evidenceId
```

Purpose: show one evidence record.

Show:

```text
target
scan run
finding, if linked
source
url
method
field
matched_value
raw_excerpt
content_hash
data JSON
created_at
```

Important:

```text
raw_excerpt should be visible
full raw response is not required for MVP
```
