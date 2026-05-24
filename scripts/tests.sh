#!/usr/bin/env bash
# Compatibility shim for the plural spelling.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/test.sh" "$@"
