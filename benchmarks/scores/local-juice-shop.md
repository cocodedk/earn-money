# Juice Shop Score Report

| Metric | Value |
|--------|-------|
| Pre-run solved | 47 / 112 |
| Post-run solved | 91 / 112 |
| Newly solved | 44 |

## Ceiling analysis (as of 2026-05-15)

Remaining 21 challenges are all blocked — not skipped. See
`docs/superpowers/specs/2026-05-15-juiceshop-solver-approach.md` for
full blocker inventory and operator actions to reach 96/112 or 112/112.

| Category | Count | Blocker |
|----------|-------|---------|
| Docker-disabled | 16 | `disabledEnv:"Docker"` — permanent on this deployment |
| Chatbot (Ollama offline) | 3 | `ollama serve` + `ollama pull gemma4:e4b` needed |
| Web3 (wallet unfunded) | 2 | ≥0.01 Sepolia ETH needed at `0x8343d2eb2B13A2495De435a1b15e85b98115Ce05` |
