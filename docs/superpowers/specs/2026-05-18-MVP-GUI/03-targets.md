# 3. Targets page

Route:

```text
/targets
```

Purpose: show all targets.

Table columns:

```text
Base URL
Host
IP
Project
Status
Created at
Actions
```

Actions:

```text
Add target
Edit target
Retire target
Delete target
Open target result
```

Add target form:

```text
project
base_url
host optional
ip optional
status default active
```

Validation:

```text
base_url is required
base_url must start with http:// or https://
project is required
```

For local fixtures, support:

```text
https://dvwa.cocode.dk
https://webgoat.cocode.dk
https://juiceshop.cocode.dk
```
