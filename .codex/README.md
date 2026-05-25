# Codex Chat Bootstrap

This directory is the Codex-side equivalent of the Claude chat hooks, scoped to
this repository only. It registers a restarted Codex session on the
`claude-chat` bus as `agent-advisor` and drains pending bus messages on
`SessionStart`, `UserPromptSubmit`, and `Stop`.

It also configures the project-local `claude-chat` MCP server at
`http://127.0.0.1:8420/sse` so the restarted session can answer through the
bus tools.

Restart from this repo with:

```bash
codex -C /home/cocodedk/0-projects/earn-money-backend
```

If Codex asks whether to trust the new hooks, approve them. The wrapper sets:

```bash
CLAUDE_AGENT_NAME=agent-advisor
CLAUDE_PROCESS_MARKER=codex
```

`CLAUDE_PROCESS_MARKER=codex` is intentional: the existing chat scripts were
written for Claude Code and otherwise look for a `claude` parent process.
