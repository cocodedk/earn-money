# 2. Projects

## 2.1 Projects page

Route:

```text
/projects
```

Purpose: manage scan projects.

Table:

```text
Name
Description
Target count
Scan run count
Created at
Actions
```

Actions:

```text
Create project
Open project
Edit project name
Delete project
```

Create project form:

```text
name
description
```

Validation:

```text
name is required
```

## 2.2 Project detail page

Route:

```text
/projects/:projectId
```

Purpose: show one project. This is the main working screen.

Sections:

```text
Project summary
Targets in this project
Recent scan runs
Recent findings
```

Actions:

```text
Add target
Create scan run
Open scan run
Open finding
```
