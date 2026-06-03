---
name: create-agent
description: Use this skill when the user wants to scaffold a new Claude-based Python agent — single-agent loops or multi-agent coordinator systems built on the Anthropic SDK. Triggers include "create an agent", "scaffold an agent", "build me an agent that…", "I need a multi-agent system for…". Generates a runnable file that follows the course conventions (haiku-4-5 pin, four-category error schema, end_turn exit, optional coordinator + hooks). Do NOT use for editing existing agents — only for greenfield creation.
---

# create-agent

Generates a new Claude-based Python agent that conforms to the **Claude Certified Architect** course conventions established in `agent.py` (single-agent loop) and `capstone_project.py` (multi-agent coordinator with hooks).

## When to invoke

Trigger when the user asks to:
- "Create / scaffold / build an agent"
- "Make me a multi-agent system for X"
- "Set up a coordinator with subagents"

Do NOT invoke for: editing an existing agent, debugging tool calls, or explaining concepts. Those use direct edits / explanations.

## How to run this skill

Follow these steps in order. Do not skip step 1 — the questions determine which template to use.

### Step 1 — Gather requirements

Ask the user for these details. If they've already supplied any in their initial request, do not re-ask — only fill in the gaps.

1. **Purpose** — what is this agent for? (one sentence)
2. **Architecture** — single-agent or multi-agent (coordinator + subagents)?
3. **Tools** — list each tool's name, what it does, and its input parameters. For each tool, ask whether it's mock data (for teaching) or a real integration.
4. **Hooks** (multi-agent only) — does the user want any PreToolUse policy gates (e.g. spend caps, auth checks) or PostToolUse normalizers (e.g. raw → human-readable)?
5. **Output filename** — default to `<purpose_snake_case>.py` in the project root if the user doesn't specify.

Use AskUserQuestion when there are 2+ clarifying questions to bundle.

### Step 2 — Pick the template

| Architecture | Template |
|---|---|
| Single-agent | `templates/single_agent.py` |
| Multi-agent (coordinator + ≥1 subagent) | `templates/multi_agent.py` |

Read the chosen template, then read `reference.md` for the non-negotiable conventions before writing.

### Step 3 — Generate the file

Write the new file using the template as a starting point. Customize:

- Tool definitions in the `tools` / `TOOLS` array (name, description, `input_schema`)
- Tool implementations in `execute_tool` / `TOOL_REGISTRY`
- Mock data dicts (use the `FAKE_DB` / `FAKE_ORDERS` style from `capstone_project.py`)
- For multi-agent: add the user's hooks to `PRE_TOOL_HOOKS` / `POST_TOOL_HOOKS`, and edit the `coordinator()` function to decompose the task into the user's subtasks
- The `if __name__ == "__main__":` block to call the entry point with a sensible example

### Step 4 — Verify

After writing, run a quick syntax check:

```bash
python -m py_compile <new_file>.py
```

If compilation passes, report the file path and the example invocation. Do not run the agent (it would hit the API and cost money) unless the user explicitly asks.

## Non-negotiable conventions

These are enforced — do not deviate without explicit user approval. See `reference.md` for the full list with rationale.

1. **Model**: `claude-haiku-4-5` only.
2. **Error schema**: tool errors must use the four categories `transient | permission | validation | internal` exactly as in `agent.py`.
3. **Loop exit**: `stop_reason == "end_turn"` is the only valid primary exit. `MAX_ITERATIONS` is a safety valve, not a stop condition.
4. **Message order**: assistant message with `tool_use` blocks is appended BEFORE the `tool_result` user message. Never reverse this.
5. **No real secrets**: mock data only. Read `ANTHROPIC_API_KEY` from env via `anthropic.Anthropic()` — never hardcode.

## Files in this skill

- `SKILL.md` — this file (entry point)
- `reference.md` — the four conventions in detail, plus the message-shape rules
- `templates/single_agent.py` — minimal single-agent loop scaffold
- `templates/multi_agent.py` — coordinator + subagent + hooks scaffold
