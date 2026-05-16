# Task 14: Manual smoke tests

Run only against authorized targets.

## Local lab

```bash
bin/probe-target \
  --platform local \
  --program juice-shop \
  --base-url http://127.0.0.1:3000 \
  --roe-profile roe/local-lab.yaml \
  --max-turns 5 \
  --max-requests 10
```

## Client target

```bash
bin/probe-target \
  --platform client \
  --program client-name \
  --base-url https://app.client.example \
  --roe-profile roe/client-name.yaml \
  --max-turns 20 \
  --max-requests 80
```

## Bug bounty target

```bash
bin/probe-target \
  --platform hackerone \
  --program program-name \
  --base-url https://target.example.com \
  --roe-profile roe/program-name.yaml \
  --max-turns 20 \
  --max-requests 80
```

Expected behavior:

* RoE profile loads
* gate runs before traffic
* allowed hosts are enforced
* denied hosts are blocked
* request budget is enforced
* methods are enforced
* disallowed test categories are denied
* target responses are marked untrusted (via `ObservationWrapper`)
* findings start as candidates
* verified findings include replay steps
* output includes stop reason and policy denials
