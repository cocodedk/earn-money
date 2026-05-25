# Clean Slate Mission Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `CLEAN_SLATE=1` option to run-mission.sh that wipes agent/scan/event data via SSH + Django management command, then runs the mission from a fresh state.

**Architecture:** `reset_lab_db` management command handles DB wipe + target seeding. `run-mission.sh` gains a CLEAN_SLATE block that SSHes to VPS and runs the command.

**Tech Stack:** Django management commands, shell scripting, pytest

---

## Tasks

| # | Task | File |
|---|------|------|
| 1 | Django management command reset_lab_db | [tasks/01-reset-command.md](tasks/01-reset-command.md) |
| 2 | Wire CLEAN_SLATE into run-mission.sh | [tasks/02-script-wiring.md](tasks/02-script-wiring.md) |
