# Lab 1.2 — Controlling Execution: Hooks, Decomposition & Session State (Optional)

Three independent demos built on the Claude Agent SDK:

| Demo | What it shows |
|---|---|
| `hooks` | A `PostToolUse` hook that logs every tool call and **blocks** any `Write`/`Edit` that targets a protected directory (e.g. `./config`). |
| `decompose` | **Fixed** decomposition (hardcoded 3-step invoice flow — used when task certainty is high) vs. **adaptive** decomposition (model decides the next step each turn, used for dynamically-branching support triage). |
| `session` | Capturing a `session_id`, then **forking** it twice to explore two solution paths (Redis vs. CDN caching) without mutating or losing the original session, each ending in a structured summary. |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

## Run

```bash
# 1. Hooks: validate/block protected-path writes
python lab_1_2.py hooks

# 2. Decomposition
python lab_1_2.py decompose --mode fixed      # invoice flow, 3 fixed steps
python lab_1_2.py decompose --mode adaptive   # support triage, branches until DONE

# 3. Session resume/fork
python lab_1_2.py session
```

## Notes / things to adapt

- **Hooks**: `post_tool_use_guard` matches on `tool_name in ("Write", "Edit")` and inspects `tool_input["file_path"]`. Adjust `PROTECTED_DIRS` for your environment. The hook return shape (`hookSpecificOutput` / `permissionDecision`) should be checked against your installed `claude-agent-sdk` version's hook contract — the field names can shift between SDK releases.
- **Decomposition**: the adaptive demo uses a simple `"DONE"` marker convention in the model's own text to decide when to stop branching. Swap this for structured JSON output if you want a more robust stop condition.
- **Session fork**: `resume=session_id` + `fork_session=True` on `ClaudeAgentOptions` is the fork mechanism — confirm these exact option names against your SDK version, as session/fork APIs are newer and may differ slightly across releases.