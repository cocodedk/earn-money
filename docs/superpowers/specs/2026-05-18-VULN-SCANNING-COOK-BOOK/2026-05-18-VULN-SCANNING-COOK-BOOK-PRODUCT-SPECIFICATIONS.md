PLAYBOOK SUGGESTED BY GPT-5.5-EXTENDED

For an authorized webapp pentest, I’d map attack vectors like this. OWASP WSTG is the base structure; PortSwigger’s academy topics are a good second source for modern web-specific classes like request smuggling, cache poisoning, GraphQL, JWT, and race conditions. ([OWASP][1])

## 1. information gathering

* Technology fingerprinting

  * framework detection
  * server headers
  * frontend framework
  * backend hints
  * package/version leaks
* Content discovery

  * hidden routes
  * backup files
  * exposed admin panels
  * old endpoints
  * debug pages
* Public metadata

  * robots.txt
  * sitemap.xml
  * security.txt
  * source maps
  * public JavaScript bundles
* Error disclosure

  * stack traces
  * verbose API errors
  * framework debug pages
  * SQL/ORM errors
* Sensitive files

  * `.env`
  * `.git`
  * config files
  * logs
  * backup archives
  * exported database files

## 2. authentication

* Weak login behavior

  * username enumeration
  * weak password policy
  * missing lockout
  * weak rate limiting
* Password reset

  * predictable reset tokens
  * token reuse
  * weak expiry
  * reset poisoning
  * account takeover via email change
* MFA

  * bypass
  * missing MFA on sensitive flows
  * weak recovery codes
  * MFA reset abuse
* OAuth / SSO

  * redirect URI issues
  * state parameter missing
  * token substitution
  * account linking flaws
  * login CSRF
* Registration

  * duplicate account confusion
  * email verification bypass
  * invitation abuse
  * tenant/org join abuse

## 3. session management

* Cookie weaknesses

  * missing `HttpOnly`
  * missing `Secure`
  * weak `SameSite`
  * broad domain scope
* Session lifecycle

  * session fixation
  * no rotation after login
  * no invalidation after logout
  * long-lived sessions
* Token handling

  * JWT algorithm confusion
  * weak signing keys
  * missing expiry
  * token accepted after logout
  * refresh token abuse
* Cross-user session issues

  * session mix-up
  * cached private data
  * concurrent session weakness

## 4. access control

* Horizontal privilege escalation

  * IDOR
  * changing object IDs
  * accessing another user’s resources
* Vertical privilege escalation

  * user to admin
  * hidden admin APIs
  * role parameter tampering
* Tenant isolation

  * cross-tenant object access
  * org ID tampering
  * workspace switching bugs
* Function-level access control

  * hidden buttons but exposed APIs
  * missing backend permission checks
  * unsafe direct API calls
* File/object access

  * private file exposure
  * predictable download URLs
  * signed URL misuse

## 5. input validation and injection

* SQL injection

  * classic SQLi
  * blind SQLi
  * second-order SQLi
  * ORM/query-builder injection
* NoSQL injection

  * Mongo-style operator injection
  * JSON query manipulation
* Command injection

  * shell command execution through parameters
  * unsafe system calls
* Server-side template injection

  * template expression injection
  * sandbox escape risk
* LDAP/XPath/XML injection

  * directory query injection
  * XML parser abuse
* Header injection

  * response splitting
  * cache poisoning helpers
* Email/template injection

  * mail header injection
  * notification template abuse

## 6. cross-site scripting

* Reflected XSS

  * query parameter reflection
  * path reflection
  * header reflection
* Stored XSS

  * comments
  * profiles
  * admin panels
  * support tickets
  * logs viewed in dashboard
* DOM XSS

  * unsafe JavaScript sinks
  * URL fragment handling
  * postMessage misuse
* Context-specific XSS

  * HTML body
  * HTML attributes
  * JavaScript strings
  * template literals
  * SVG
* CSP weaknesses

  * missing CSP
  * unsafe-inline
  * weak script sources
  * JSONP or callback bypasses

## 7. CSRF and browser-side request abuse

* State-changing requests without CSRF protection
* Weak CSRF token validation
* Token not tied to session
* SameSite bypass conditions
* Login CSRF
* GraphQL CSRF
* CORS-assisted CSRF-style abuse

## 8. file upload and file handling

* Dangerous file types

  * executable upload
  * script upload
  * SVG with script
  * HTML upload
* Content-type bypass

  * MIME mismatch
  * extension tricks
  * polyglot files
* Storage issues

  * public upload paths
  * predictable filenames
  * overwrite attacks
* Image/file processing

  * parser crashes
  * metadata leakage
  * decompression bombs
* Path handling

  * path traversal in upload name
  * arbitrary file write

## 9. path traversal and file inclusion

* Local file read
* Directory traversal
* Unsafe download endpoints
* Template/file include bugs
* Static file bypass
* Archive extraction traversal
* Log file exposure
* Source code exposure

## 10. server-side request forgery

* Internal service access
* Cloud metadata access
* Localhost-only admin interfaces
* URL parser confusion
* Redirect-based SSRF
* DNS rebinding-style issues
* Blind SSRF
* SSRF through webhooks, importers, previews, PDF generators

## 11. API security

* REST API issues

  * missing auth
  * broken object-level authorization
  * over-broad responses
  * mass assignment
* GraphQL

  * introspection exposure
  * authorization gaps per resolver
  * query depth abuse
  * batching abuse
  * alias-based rate limit bypass
* WebSockets

  * missing auth on socket connect
  * message-level auth bugs
  * cross-user message access
* gRPC/internal APIs

  * exposed debug endpoints
  * reflection exposure
  * weak service auth
* Versioned APIs

  * old vulnerable versions
  * deprecated endpoints still active

## 12. business logic

* Workflow bypass

  * skipping required steps
  * direct API calls out of order
* Price/payment manipulation

  * quantity tampering
  * coupon abuse
  * negative values
  * currency mismatch
* State confusion

  * race between states
  * invalid transitions
* Approval bypass

  * self-approval
  * role confusion
  * stale permissions
* Abuse of limits

  * trial abuse
  * invitation abuse
  * quota bypass
  * refund/credit abuse

## 13. race conditions

* Double spending
* Coupon reuse
* Multiple password reset use
* Limit bypass
* Concurrent order/state changes
* Multi-endpoint race bugs
* Partial object creation abuse

## 14. deserialization and object parsing

* Insecure deserialization
* Unsafe YAML/XML parsing
* Pickle/Java/.NET object handling
* Prototype pollution
* Parser differentials
* Type confusion in JSON/body parsing

## 15. client-side security

* Sensitive data in JavaScript

  * API keys
  * hidden endpoints
  * feature flags
  * internal routes
* Source maps

  * source code leakage
  * comments and TODOs
* postMessage

  * missing origin checks
  * unsafe message handling
* Local storage/session storage

  * tokens stored unsafely
  * sensitive user data
* Client-side access control only

  * hidden UI controls
  * disabled buttons with exposed APIs

## 16. CORS and cross-origin policy

* Wildcard origins with credentials
* Origin reflection
* Null origin trust
* Over-trusted subdomains
* Over-exposed headers
* Misconfigured preflight behavior

## 17. HTTP request/response handling

* HTTP request smuggling
* HTTP response splitting
* Host header attacks
* Cache poisoning
* Web cache deception
* Content-type confusion
* Method override abuse
* Parameter pollution

## 18. security headers and browser hardening

* Missing CSP
* Missing HSTS
* Missing X-Frame-Options / frame-ancestors
* Missing Referrer-Policy
* Missing Permissions-Policy
* Weak cookie attributes
* MIME sniffing allowed
* Clickjacking exposure

## 19. cryptography and secrets

* Hardcoded secrets
* Weak token generation
* Predictable IDs
* Weak random values
* Sensitive data in URLs
* Insecure password storage hints
* Weak encryption mode
* Missing signing or integrity checks

## 20. logging, monitoring, and privacy

* Sensitive data in logs
* Secrets in error responses
* PII overexposure
* Insecure analytics/debug tooling
* Audit log tampering
* Missing audit trail for sensitive actions
* Log injection

## 21. infrastructure and deployment exposure

* Exposed admin panels
* Debug ports
* Staging environment indexed
* Default credentials
* Misconfigured reverse proxy
* Directory listing
* Cloud bucket exposure
* Container metadata leaks
* CI/CD artifact exposure

## 22. third-party integrations

* Webhook abuse
* OAuth app misconfiguration
* Payment provider callback tampering
* SAML misconfiguration
* Email/SMS provider abuse
* Unsafe import/export integrations
* Trusting third-party callback data without verification

## 23. denial of service, within RoE

* Expensive search queries
* Large file upload processing
* Regex backtracking
* GraphQL query depth
* Pagination abuse
* Resource-heavy report generation
* Rate limit gaps

## 24. AI/LLM-specific webapp vectors, if the app uses AI

* Prompt injection
* Indirect prompt injection through webpages/files
* Tool-call manipulation
* Data exfiltration through model output
* Retrieval poisoning
* Cross-user memory leakage
* Unsafe agent actions
* Insecure plugin/tool permissions
* Model output trusted as policy decision

For your scanner engine, this list becomes a coverage map: each discovered input, endpoint, form, script, header, cookie, and workflow gets tagged against one or more of these categories, then the engine chooses safe tests from the allowed RoE.

[1]: https://owasp.org/www-project-web-security-testing-guide/?utm_source=chatgpt.com "OWASP Web Security Testing Guide"
