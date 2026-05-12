#!/bin/sh
# Apply repository settings and branch protection.
# Prerequisites: gh CLI authenticated with admin rights on the repo.
# Run once, after the repo has been created and the first commit pushed.
set -eu

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
OWNER=$(gh repo view --json owner -q .owner.login)

echo ""
echo "=== Repository setup: $REPO ==="
echo ""

# ── Merge strategy ────────────────────────────────────────────────────────────
gh repo edit "$REPO" \
  --delete-branch-on-merge \
  --enable-squash-merge \
  --enable-rebase-merge \
  --enable-merge-commit=false

echo "ok: merge strategy = squash + rebase only, auto-delete head branches"

# ── Branch protection ─────────────────────────────────────────────────────────
# Solo private operations repo: no required reviews, no required status checks
# (no CI workflow yet — add status check requirement when CI lands).
# Strong guardrails on history and force-push; admins included.
gh api \
  --method PUT \
  "/repos/$REPO/branches/$DEFAULT_BRANCH/protection" \
  --input - <<'PROTECTION_EOF'
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true,
  "required_conversation_resolution": false
}
PROTECTION_EOF

echo "ok: branch protection on $DEFAULT_BRANCH"

# ── CODEOWNERS ────────────────────────────────────────────────────────────────
mkdir -p .github
printf '# All files — repo owner review on every PR.\n* @%s\n' "$OWNER" \
  > .github/CODEOWNERS

echo "ok: .github/CODEOWNERS written"
echo ""
echo "Active on $DEFAULT_BRANCH:"
echo "  - No force pushes"
echo "  - No branch deletion"
echo "  - Linear history (squash + rebase merges only)"
echo "  - Applies to admins"
echo ""
echo "When CI lands: edit this script to set"
echo "  required_status_checks = { strict: true, contexts: [\"<job-name>\"] }"
echo "and rerun it."
echo ""
echo "Next:"
echo "  git add .github/CODEOWNERS && git commit -m 'chore: add CODEOWNERS'"
