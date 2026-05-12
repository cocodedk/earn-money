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
#
# Note: classic branch protection on private repos requires GitHub Pro.
# On free private repos this call returns 403 — we warn and continue so
# the rest of the script (merge strategy, CODEOWNERS) still applies.
PROTECTION_BODY='{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true,
  "required_conversation_resolution": false
}'

PROTECTION_APPLIED=0
if printf '%s' "$PROTECTION_BODY" | gh api --method PUT \
     "/repos/$REPO/branches/$DEFAULT_BRANCH/protection" \
     --input - >/dev/null 2>&1; then
  echo "ok: branch protection on $DEFAULT_BRANCH"
  PROTECTION_APPLIED=1
else
  echo "warn: branch protection skipped — likely a free private repo (needs GitHub Pro)."
  echo "      The pre-push hook still enforces the owner-lock client-side."
fi

# ── CODEOWNERS ────────────────────────────────────────────────────────────────
mkdir -p .github
printf '# All files — repo owner review on every PR.\n* @%s\n' "$OWNER" \
  > .github/CODEOWNERS

echo "ok: .github/CODEOWNERS written"
echo ""
if [ "$PROTECTION_APPLIED" = "1" ]; then
  echo "Active on $DEFAULT_BRANCH (server-enforced):"
  echo "  - No force pushes"
  echo "  - No branch deletion"
  echo "  - Linear history"
  echo "  - Applies to admins"
else
  echo "Server-side branch protection is NOT active on $DEFAULT_BRANCH."
  echo "Client-side safety net active via pre-push hook (owner-lock only)."
  echo "To enable server-side protection: upgrade to GitHub Pro or make the repo public,"
  echo "then rerun this script."
fi
echo ""
echo "When CI lands: edit this script to set"
echo "  required_status_checks = { strict: true, contexts: [\"<job-name>\"] }"
echo "and rerun it."
