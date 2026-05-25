#!/usr/bin/env bash
set -euo pipefail

event="${1:-UserPromptSubmit}"
chat_root="${CHAT_ROOT:-$HOME/0-projects/claude-email}"
agent_name="${CODEX_CHAT_AGENT_NAME:-agent-advisor}"
cat >/dev/null || true
hook_payload="{\"hook_event_name\":\"$event\"}"

export CLAUDE_AGENT_NAME="$agent_name"
export CLAUDE_PROCESS_MARKER="${CODEX_PROCESS_MARKER:-codex}"

if [[ ! -x "$chat_root/scripts/chat-register-self.py" ]]; then
  echo "chat-agent-advisor-hook: missing $chat_root/scripts/chat-register-self.py" >&2
  exit 0
fi

printf '%s' "$hook_payload" | "$chat_root/scripts/chat-register-self.py" >&2 || true

case "$event" in
  SessionStart|UserPromptSubmit|Stop)
    if [[ -x "$chat_root/scripts/chat-drain-inbox.py" ]]; then
      printf '%s' "$hook_payload" | "$chat_root/scripts/chat-drain-inbox.py" || true
    fi
    ;;
esac
