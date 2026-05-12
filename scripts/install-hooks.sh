#!/bin/sh
set -eu
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/commit-msg .githooks/pre-push
echo "Hooks installed:"
echo "  pre-commit  — blocks staged sensitive paths"
echo "  commit-msg  — enforces Conventional Commits"
echo "  pre-push    — owner-locked to github.com/cocodedk"
