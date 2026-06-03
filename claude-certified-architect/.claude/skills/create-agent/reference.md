# create-agent — reference conventions

These rules come from `agent.py` and `capstone_project.py`. They are course-level conventions, not personal style — keep them intact unless the user explicitly overrides.

## 1. Model pinning

```python
MODEL = "claude-haiku-4-5"
```

Reason: cost + speed for learners. Do NOT bump to Sonnet/Opus without an explicit ask. The course materials assume haiku-4-5 latency and cost.

## 2. Four-category error schema

Every `handle_tool_call` must return a `tool_result` dict for both success AND every error path. Never let an exception bubble out of `handle_tool_call`. The four categories:

| Category | Trigger | `isRetryable` | Extra fields |
|---|---|---|---|
| `transient` | `TimeoutError` | `true` | `retryAfterMs` |
| `permission` | `PermissionError` | `false` | — |
| `validation` | `ValueError` | `false` | — |
| `internal` | bare `Exception` | `false` | — |

Each error response shape:

```python
{
    "type":        "tool_result",
    "tool_use_id": tool_id,
    "is_error":    True,
    "content":     json.dumps({
        "errorCategory": "<category>",
        "isRetryable":   <bool>,
        "description":   "<human readable>",
        # plus retryAfterMs only for transient
    }),
}
```

Reason: structured categories let the agent (or coordinator) decide retry vs self-correct vs escalate.

## 3. Agentic loop exit

```python
if response.stop_reason == "end_turn":
    return <text>
```

This is the only valid primary exit. `MAX_ITERATIONS` is a safety valve — when it fires, return an error string, do not silently succeed.

```python
MAX_ITERATIONS = 50  # safety valve, not stop condition
```

## 4. Message ordering on tool_use

When `stop_reason == "tool_use"`:

1. **First**, append the assistant message containing the tool_use blocks:
   ```python
   messages.append({"role": "assistant", "content": response.content})
   ```
2. **Then**, run every tool and append a single user message with all tool_results:
   ```python
   messages.append({"role": "user", "content": tool_results})
   ```

Never reverse these. Never combine multiple turns into one append.

## 5. Tool descriptions — the four levers

When writing `description` for a tool schema, cover all four:

1. WHAT it does — so the model picks the right tool
2. WHEN to call it — ordering and prerequisites ("call get_customer first")
3. WHAT NOT to use it for — prevents common mix-ups
4. WHAT it returns — so the model knows the shape it'll get back

## 6. Multi-agent only — hooks

PreToolUse hooks run BEFORE the tool. They can BLOCK by returning `{"allowed": False, "reason": "..."}`. Use for: spend caps, auth gates, destructive-action review.

PostToolUse hooks run AFTER the tool, BEFORE the model sees the result. Use for: normalizing raw data (status codes → words, Unix ts → dates, cents → dollars), updating session state.

Hooks are registered in ordered lists `PRE_TOOL_HOOKS` and `POST_TOOL_HOOKS`. First Pre hook to return `allowed=False` wins. Every Post hook runs in order, each seeing the previous output.

## 7. Subagent context isolation (multi-agent)

A subagent gets ONLY the tools and context the coordinator explicitly hands it:

```python
verification_finding = run_subagent(
    role="Customer Verifier",
    task_prompt=...,
    tools=[TOOLS[0]]   # only get_customer — not the full TOOLS array
)
```

Findings are passed to the next subagent as **structured dicts**, not free-form prose:

```python
return {
    "subagent_role": role,
    "task":          task_prompt[:100],
    "result":        result_text,
    "status":        "complete"
}
```

## 8. No secrets

- API key: read from `ANTHROPIC_API_KEY` env via `anthropic.Anthropic()` — never hardcoded.
- Tool data: mock dicts only (`FAKE_DB`, `FAKE_ORDERS` style). No real customer records.
