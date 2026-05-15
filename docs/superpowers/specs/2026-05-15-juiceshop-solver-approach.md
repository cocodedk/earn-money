# Juice Shop Solver Approach — Decision Artifact

**Context:** `bin/juice-shop-run` is running against target.cocode.dk.
The pipeline is stuck on nuclei-scan (8,025 templates × 10 rps ≈ 30-60 min).
Pre-snapshot: 47/112 solved. Four prior nuclei runs found only swagger-api,
http-missing-security-headers, and prometheus-metrics — zero challenge-solving
signals. katana and subzy are not installed; takeover, sqli-probe, and
xss-probe steps produce no output.

## Options

### A — Kill nuclei, reduce to targeted set
Kill the active nuclei scan process (identified via `ps aux | grep nuclei` by
command signature, not hard-coded PID). Restrict roe.md to
`http/exposures + http/misconfiguration`.
Install katana locally so sqli-probe and xss-probe can run next invocation.

Pros: faster cycle, activates purpose-built probes.
Cons: nuclei injection/xss templates still won't map to Juice Shop challenge
verification — those challenges require specific payloads, not generic template
matches.

### B — Let nuclei complete, then iterate
Wait 30-60 min; add katana in parallel for next run.

Pros: no lost work.
Cons: first run produces near-zero challenge delta; the 8,025 templates are
generic and Juice Shop's challenge solver expects exact trigger patterns, not
just any SQL error or reflected string.

### C — Kill nuclei, build a dedicated JuiceShop challenge solver runner
A new `juiceshop_solver` runner that reads `/api/Challenges`, groups unsolved
by category, and fires purpose-built HTTP requests per challenge class:

- **Score Board** — `GET /score-board` via httpx; Juice Shop marks this solved
  server-side when the route is visited (the challenge listener watches the
  REST endpoint, not the SPA router)
- **Admin Section** — GET /administration after JWT alg:none bypass
- **Zero Stars** — POST /api/Feedbacks with rating=0
- **Login Admin** — POST /api/Users/login with `' OR 1=1--` payload
- **Login Bjoern** — use known Juice Shop fixture account (mc.safesearch@juice-sh.op)
  via security-question reset flow; bounded to 1 reset attempt, not enumeration
- **Exposed Metrics** — GET /metrics
- **Privacy Policy** — GET /privacy-security/privacy-policy
- **View Basket** — GET /rest/basket/:id auth-bypass
- **Forged Feedback** — POST /api/Feedbacks with forged userId
- **XSS Tier 1 (DOM)** — GET /redirect?to= with `<iframe src=javascript:alert()>`
- **XSS Tier 2 (Stored)** — PUT /api/Products/1 body `{"description":"<iframe>…"}`
- **XSS Tier 3 (API-only)** — PUT /api/Users/1 via forged JWT with iframe name
- **SQL Tier 1 (Login)** — POST /api/Users/login body `{"email":"' OR 1=1--"}`
- **SQL Tier 2 (Search)** — GET /rest/products/search?q=` (backtick injection)
- **SQL Tier 3 (Union)** — GET /rest/products/search?q=`))UNION SELECT...--
- **IDOR/Basket** — GET /rest/basket/2 with user-1 JWT
- **Forgotten Developer Backup** — GET /ftp/coupons_2013.md.bak
- **Confidential Document** — GET /ftp/acquisitions.md
- **Christmas Special** — search via SQL for deleted product
- **User Credentials** — GET /api/Users via JWT alg:none
- **Admin Registration** — POST /api/Users with role=admin field (mass-assign)
- **Exposed Metrics** — GET /metrics (already in auth-bypass-probe scope)
- **Privacy Policy** — GET /privacy-security/privacy-policy
- **Missing Encoding** — craft URL with unencoded ß character
- **Forged Feedback** — POST /api/Feedbacks with UserId not matching token
- **Zero Stars** — POST /api/Feedbacks with rating=0
- (Full exhaustive list goes into the implementation plan; ~40 challenges
  targeted across Injection, Broken Access, XSS, IDOR, Insecure Deserialization,
  Security Misconfiguration, Sensitive Data Exposure categories)

Pros: only path to 30-90% coverage; directly maps challenge semantics to HTTP
actions; each category is a deterministic function, not a template heuristic.
Cons: more code (est. 300-400 lines split across tool + runner); needs design
review before implementation.

## Decision

**C — dedicated JuiceShop challenge solver, kill current nuclei run.**

Rationale:
1. Nuclei templates are generalist; Juice Shop challenges require exact trigger
   sequences that no existing nuclei template implements.
2. The auth-bypass-probe already handles JWT alg:none and admin path probing —
   but doesn't map findings back to challenge completion.
3. A dedicated solver is the only approach that can clear the majority of the
   112 challenges autonomously.
4. The existing pipeline (httpx, auth-bypass, graphql, sourcemap) continues to
   run; the solver is an additive step, not a replacement.
5. nuclei is retained in the pipeline. The `extra_nuclei_dirs` in
   `programs/local/juice-shop/roe.md` are cleared (removing the 3 extra dirs
   added for this program). The pipeline's hard-coded base approved dirs —
   cves, exposed-panels, exposures, misconfiguration, takeovers — remain active.
   This cuts the template count from 8,025 to ~500.

## Implementation Outline

### Files
- `src/earn_money/recon/juiceshop_solver_tool.py` — HTTP action library
  (challenge-id → HTTP sequence → bool solved)
- `src/earn_money/runners/juiceshop_solver.py` — runner that calls tool,
  writes Signals, saves solved IDs to DB
- `src/earn_money/runners/juiceshop_solver_cli.py` — standalone CLI
- `tests/recon/test_juiceshop_solver_tool.py`
- `tests/runners/test_juiceshop_solver.py`

### Safety constraints (unchanged)
- Only targets assets loaded from the program's `scope.md` at runtime (no
  hardcoded URLs in implementation code)
- roe.md `auth_testing_authorized: true` gates auth-bypass techniques
- `dos_authorized: false` — no flood/rate attacks
- Signals written to DB; no automatic findings promotion past gate 1

### Nuclei scope reduction
Edit `programs/local/juice-shop/roe.md`: set `extra_nuclei_dirs: []` (clear
the list). The pipeline's hard-coded base approved dirs — cves, exposed-panels,
exposures, misconfiguration, takeovers — remain active via `nuclei_scan_cli.py`,
reducing total template count from 8,025 to ~500 and scan time from 30-60 min
to 3-5 min. No new roe.md field is introduced.

## Decisions

- **Why not B?** Waiting 60 min for zero delta is wasteful and blocks the
  iteration loop.
- **Why not A only?** Reducing nuclei + installing katana adds probes for
  generic SQLi/XSS, but Juice Shop's challenge unlock requires the exact
  solver payload sequence, not just any injection signal.
- **Nuclei retained?** Yes — it detects real misconfiguration signals. The
  scope reduction is only for this program's roe.md, not global.
