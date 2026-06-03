---
description: Scaffold a new Claude-based Python agent that follows the course conventions
argument-hint: [one-line description of the agent — or leave blank to be prompted]
allowed-tools: Read, Write, Edit, Bash(python -m py_compile:*), Bash(ls:*)
---

# /create-agent

You are scaffolding a brand-new Claude-based Python agent for the **Claude Certified Architect** course project. The user invoked this command explicitly — they want a runnable file at the end, not a discussion.

User's request: **$ARGUMENTS**

(If `$ARGUMENTS` is empty, ask the user for a one-line description before continuing.)

## Reference files — read these first

Before writing anything, read both reference implementations so the new file matches their shape exactly:

- @agent.py — single-agent loop with the four-category error schema
- @capstone_project.py — coordinator + subagents + Pre/Post hooks
- @CLAUDE.md — project-wide conventions

## What to do

1. **Confirm shape** — based on `$ARGUMENTS`, decide single-agent vs multi-agent (coordinator). If ambiguous, ask one short question. Otherwise proceed.

2. **Confirm tools** — list the tool names + purposes you plan to include and ask the user to confirm or edit. Skip this step only if `$ARGUMENTS` already names the tools.

3. **Write the file** — create `<purpose_snake_case>.py` in the project root, mirroring the structure of `agent.py` (single) or `capstone_project.py` (multi).

4. **Verify** — run `python -m py_compile <new_file>.py`. Fix any syntax errors before returning.

5. **Report** — give the user the file path and one-line example invocation. Do not run the agent itself (it costs API tokens).

## Non-negotiable conventions

These are enforced by `CLAUDE.md`:

- **Model**: `claude-haiku-4-5` only. Do not bump.
- **Error schema**: tool errors must use the four categories `transient | permission | validation | internal`. Match `agent.py:74-149` exactly.
- **Loop exit**: `stop_reason == "end_turn"` is the only valid primary exit. `MAX_ITERATIONS = 50` is a safety valve.
- **Message order**: append the assistant message containing tool_use blocks BEFORE the tool_result user message. Never reverse.
- **Mock data only** — `FAKE_DB` / `FAKE_ORDERS` style. Read `ANTHROPIC_API_KEY` from env via `anthropic.Anthropic()`. Never hardcode secrets.
- **Multi-agent**: subagents receive only the tools the coordinator hands them; findings flow as structured dicts (see `capstone_project.py:454-460`), not prose.

## Style

- Keep teaching comments where they explain WHY (model pin, append-order, error categories). Drop comments that just restate WHAT.
- No real API integrations — mock dicts only.
- File should be runnable: include an `if __name__ == "__main__":` block with a sensible example call.
