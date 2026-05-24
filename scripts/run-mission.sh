#!/bin/sh
# Start a V3 agent mission and stream progress until completion.
#
# Usage:
#   ./scripts/run-mission.sh <target-host-or-uuid>
#   ./scripts/run-mission.sh juiceshop.cocode.dk
#   ./scripts/run-mission.sh 0be02808-dc57-4560-9688-bbd3fd1fca83
#
# Options (env):
#   API_BASE=http://localhost   — API base URL (nginx on port 80)
#   PROFILE=juice_shop_scoreboard
#   TIMEOUT=600                 — max seconds to wait for completion
#   DRY_RUN=1                   — resolve target and print POST payload only

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { printf "${GREEN}[mission]${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}[mission]${NC} %s\n" "$1" >&2; }
die() { printf "${RED}[mission]${NC} %s\n" "$1" >&2; exit 1; }

TARGET_ARG="${1:-}"
[ -z "$TARGET_ARG" ] && die "Usage: $0 <target-host-or-uuid>"

API_BASE="${API_BASE:-http://localhost}"
PROFILE="${PROFILE:-juice_shop_scoreboard}"
TIMEOUT="${TIMEOUT:-600}"
DRY_RUN="${DRY_RUN:-0}"
STATUS="timeout"
TURNS=0

case "$TIMEOUT" in
  ''|*[!0-9]*) die "TIMEOUT must be a positive integer, got '$TIMEOUT'" ;;
esac
[ "$TIMEOUT" -gt 0 ] || die "TIMEOUT must be greater than zero"

# Helper: safe JSON parse — dies with message instead of traceback
pyjson() {
  python3 -c "
import sys, json
raw = sys.stdin.read()
if not raw.strip():
    sys.exit(1)
try:
    d = json.loads(raw)
except json.JSONDecodeError:
    sys.exit(1)
$1
"
}

# --- Resolve target (UUID or host lookup) ---
case "$TARGET_ARG" in
  *-*-*-*-*) TARGET_ID="$TARGET_ARG" ;;
  *)
    log "looking up target: $TARGET_ARG"
    TARGET_ID=$(python3 -c "
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

api_base = sys.argv[1].rstrip('/')
host = sys.argv[2]
url = f'{api_base}/api/targets/?page_size=200'
matches = []

try:
    while url:
        with urlopen(url, timeout=30) as resp:
            data = json.load(resp)
        matches.extend(t for t in data.get('results', []) if t.get('host') == host)
        url = data.get('next')
except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
    print(f'failed to fetch targets: {exc}', file=sys.stderr)
    sys.exit(2)

if len(matches) > 1:
    print('ambiguous target host; use one of these UUIDs:', file=sys.stderr)
    for m in matches:
        print(f'  {m.get(\"id\", \"?\")}  {m.get(\"base_url\", \"?\")}', file=sys.stderr)
    sys.exit(3)

print(matches[0].get('id', '') if matches else '')
" "$API_BASE" "$TARGET_ARG") || die "Target lookup failed for '$TARGET_ARG'"
    [ -z "$TARGET_ID" ] && die "No target with host '$TARGET_ARG'"
    ;;
esac

export TARGET_ID PROFILE
log "target ID: $TARGET_ID"

if [ "$DRY_RUN" = "1" ]; then
  log "DRY_RUN: would POST $API_BASE/api/agent/sessions/"
  python3 -c "
import json
import os
print(json.dumps({
    'target': os.environ['TARGET_ID'],
    'mission_profile': os.environ['PROFILE'],
}, indent=2))
"
  exit 0
fi

# --- Start mission ---
log "starting mission (profile=$PROFILE)"
SESSION=$(curl -sf -X POST "$API_BASE/api/agent/sessions/" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json, os
print(json.dumps({
    'target': os.environ['TARGET_ID'],
    'mission_profile': os.environ['PROFILE'],
}))
")") || die "Failed to create session (API error or unreachable)"

# Parse session response once
PARSED=$(echo "$SESSION" | pyjson "
sid = d.get('id', '')
phases = ' -> '.join(d.get('active_phases', ['?']))
budget = d.get('mission_budget', {}).get('max_turns', '?')
print(f'{sid}|{phases}|{budget}')
") || die "Invalid session response"

SESSION_ID=$(echo "$PARSED" | cut -d'|' -f1)
PHASES=$(echo "$PARSED" | cut -d'|' -f2)
BUDGET=$(echo "$PARSED" | cut -d'|' -f3)
[ -z "$SESSION_ID" ] && die "Session response missing 'id'"

log "session: $SESSION_ID"
log "phases: $PHASES"
log "budget: $BUDGET turns"
log "timeout: ${TIMEOUT}s"
echo ""

# --- Poll until terminal or timeout ---
PREV=""
FAIL_COUNT=0
START=$(date +%s)
while true; do
  ELAPSED=$(( $(date +%s) - START ))
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    warn "timeout after ${TIMEOUT}s — session may still be running"
    break
  fi

  DATA=$(curl -sf "$API_BASE/api/agent/sessions/$SESSION_ID/" 2>/dev/null || echo "")
  if [ -z "$DATA" ]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
    if [ "$FAIL_COUNT" -ge 10 ]; then
      die "API unreachable after 10 consecutive failures"
    fi
    sleep 3
    continue
  fi
  FAIL_COUNT=0

  # Parse all three fields in one Python call
  POLL=$(echo "$DATA" | pyjson "
s = d.get('status', 'unknown')
p = d.get('current_phase', '?')
t = d.get('consumed_budget', {}).get('mission', {}).get('turns', 0)
print(f'{s}|{p}|{t}')
" 2>/dev/null) || { sleep 5; continue; }

  STATUS=$(echo "$POLL" | cut -d'|' -f1)
  PHASE=$(echo "$POLL" | cut -d'|' -f2)
  TURNS=$(echo "$POLL" | cut -d'|' -f3)

  LINE="$STATUS | $PHASE | $TURNS/$BUDGET turns"
  if [ "$LINE" != "$PREV" ]; then
    printf "${CYAN}[%s]${NC} %s\n" "$(date +%H:%M:%S)" "$LINE"
    PREV="$LINE"
  fi

  case "$STATUS" in
    completed|stopped|failed) break ;;
  esac
  sleep 5
done

echo ""

# --- Show results ---
log "mission $STATUS after $TURNS turns"
log "fetching turn summary..."
echo ""

EXIT_STATUS=0
case "$STATUS" in
  completed) EXIT_STATUS=0 ;;
  *) EXIT_STATUS=1 ;;
esac

TURNS_JSON=$(curl -sf "$API_BASE/api/agent/sessions/$SESSION_ID/turns/" || echo "")
echo "$TURNS_JSON" | pyjson "
for t in d.get('results', []):
    acts = t.get('actions', [])
    a = acts[0] if acts else {}
    goal = a.get('goal', '')[:65]
    atype = a.get('action_type', '?')
    phase = t.get('phase', '?')
    vs = a.get('validation_status', '?')
    print(f'  Turn {t.get(\"index\", 0):2d} | {phase:9s} | {atype:22s} | {vs:14s} | {goal}')
" 2>/dev/null || { warn "Could not fetch turn data"; EXIT_STATUS=1; }

echo ""

NOTES_JSON=$(curl -sf "$API_BASE/api/agent/sessions/$SESSION_ID/notes/" || echo "")
echo "$NOTES_JSON" | pyjson "
notes = d.get('results', [])
if notes:
    print('  Notes:')
    for n in notes:
        print(f'    {n.get(\"note_type\", \"?\")}: {json.dumps(n.get(\"content\", {}))[:80]}')
else:
    print('  No notes recorded.')
" 2>/dev/null || { warn "Could not fetch notes"; EXIT_STATUS=1; }

exit "$EXIT_STATUS"
