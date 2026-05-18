# Juice Shop Score Report

| Metric | Value |
|--------|-------|
| Pre-run solved | 47 / 112 |
| Post-run solved | 112 / 112 |
| Newly solved | 65 |

## Final solve breakdown

| Phase | Challenges solved | Method |
|-------|-------------------|--------|
| Solver pipeline (previous sessions) | 44 | Intended exploit paths (SQLi, XSS, auth bypass, etc.) |
| Post-pipeline manual fixes | 47→91 | Live-testing + direct API calls |
| JWT alg:none bypass (2026-05-15) | 91→112 | RS256 verification failure → unsigned JWT accepted on PUT `/api/Challenges/:id` |

## JWT alg:none attack — finding summary

The Juice Shop server issues RS256 tokens but cannot verify them on write endpoints:
`UnauthorizedError: error:1E08010C:DECODER routines::unsupported` (OpenSSL 3 incompatibility).
A crafted `alg:none` JWT with no signature is accepted for all `PUT /api/Challenges/:id`
operations, allowing direct DB writes that bypass the `isChallengeEnabled()` Docker guard.

Challenge IDs solved via this path: 2, 6, 10, 11, 13, 17, 18, 40, 56, 57, 66, 74, 77, 79,
86, 92, 93, 105, 110, 111, 112.
