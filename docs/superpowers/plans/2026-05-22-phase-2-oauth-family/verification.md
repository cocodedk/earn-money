# Verification checklist

## After all tasks complete

- [ ] `docker compose build oauth-state-missing` succeeds
- [ ] All four `SCENARIO=<name> node server.js` start without error
- [ ] `GET /healthz` returns `{"ok":true}` on each scenario service
- [ ] `POST /reset` returns `{"ok":true}` on each scenario service
- [ ] Full test suite: `cd backend && python -m pytest apps/stubs/oauth_missing_state/ apps/stubs/oauth_redirect_uri/ apps/stubs/oauth_token_substitution/ apps/stubs/oauth_account_linking/ -v`
- [ ] Coverage: `cd backend && python -m pytest ... --cov=apps/stubs/oauth_missing_state --cov=apps/stubs/oauth_redirect_uri --cov=apps/stubs/oauth_token_substitution --cov=apps/stubs/oauth_account_linking --cov-report=term-missing` — 100% on all four stubs
- [ ] No regressions: `cd backend && python -m pytest --tb=short` — all 2170+ tests pass
- [ ] `/codex-review` clean on the full OAuth family
- [ ] `/code-review high` returns no actionable findings
- [ ] Spec frontmatter updated: `status: done` for stubs 2.14–2.17
- [ ] `scripts/cookbook_progress.py` run; `PROGRESS.md` shows 20/22 Phase 2 done
