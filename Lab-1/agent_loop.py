"""
agent_loop.py

The core agentic loop primitive used by every agent in this lab
(orchestrator AND every subagent). This is the piece most implementations
get subtly wrong, so it is isolated here as a single, well-tested function.

THE CENTRAL IDEA
-----------------
Claude's API response always has a `stop_reason` field. A stable agent loop
is fundamentally a state machine keyed off that field:

    stop_reason == "tool_use"     -> Claude wants to act. Execute the
                                      requested tool(s), append the results
                                      as a `tool_result` user message, and
                                      call the API again. LOOP CONTINUES.

    stop_reason == "end_turn"     -> Claude is done. It produced a final
                                      answer with no pending tool calls.
                                      LOOP HALTS.

    stop_reason == "max_tokens"   -> Claude was cut off mid-generation.
                                      This is NOT the same as "done." If you
                                      treat this like end_turn you silently
                                      ship truncated output. We treat this
                                      as an error condition to surface,
                                      not a stopping point to accept.

    stop_reason == "stop_sequence"-> A custom stop sequence fired. Treat as
                                      halt, but the caller should check
                                      which sequence fired if it matters.

    stop_reason == "pause_turn"   -> Used with server-side tools (e.g. web
                                      search) on long-running turns. The
                                      correct action is to simply continue
                                      the loop by sending the conversation
                                      back as-is (Claude continues where it
                                      left off). It is NOT a halt and NOT a
                                      local tool-execution step.

    stop_reason == "refusal"      -> Claude declined to continue for policy
                                      reasons. LOOP HALTS. Do not retry the
                                      same request in a loop.

A very common bug: code that only checks `if stop_reason != "tool_use": break`.
That treats max_tokens and refusal as if they were a clean finish. This
module makes the distinction explicit and auditable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import anthropic


# --------------------------------------------------------------------------
# Result wrapper so callers always know HOW the loop ended, not just WHAT
# the final text was. This is what makes the loop's behavior testable.
# --------------------------------------------------------------------------

@dataclass
class LoopResult:
    final_text: str
    stop_reason: str
    turns_used: int
    halted_cleanly: bool          # True only for end_turn / stop_sequence
    truncated: bool                # True if any turn hit max_tokens
    tool_calls_made: list[dict] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)  # full message log
    error: Optional[str] = None


class MaxTurnsExceeded(Exception):
    """Raised when the loop runs longer than the configured safety cap.

    A stable agentic loop MUST have a hard ceiling on turns. Without one,
    a model stuck in a tool_use/tool_result cycle (e.g. a flaky tool that
    keeps returning an error the model keeps retrying) will run forever
    and burn tokens/money indefinitely.
    """


def run_agent_loop(
    client: anthropic.Anthropic,
    *,
    model: str,
    system: str,
    messages: list[dict],
    tools: list[dict],
    tool_executor: Callable[[str, dict], str],
    max_turns: int = 8,
    max_tokens: int = 2000,
    verbose: bool = True,
    agent_name: str = "agent",
) -> LoopResult:
    """
    Run a single agent (orchestrator OR subagent) to completion using the
    stop_reason state machine described above.

    Parameters
    ----------
    client          : anthropic.Anthropic instance
    model           : model string, e.g. "claude-sonnet-4-6"
    system          : system prompt for this agent
    messages        : starting message list (mutated copy is returned in
                       result.transcript; caller's list is not mutated)
    tools           : tool schema list passed to the API
    tool_executor   : fn(tool_name, tool_input_dict) -> str (tool result text)
    max_turns       : hard ceiling on API round-trips (safety valve)
    max_tokens      : per-call max_tokens budget
    verbose         : print loop progress
    agent_name      : label used in verbose logs, helps when multiple
                       agents' logs are interleaved (orchestrator + subagents)

    Returns
    -------
    LoopResult capturing exactly how the loop ended.
    """
    msgs = [dict(m) for m in messages]  # local mutable copy
    tool_calls_made: list[dict] = []
    truncated = False

    for turn in range(1, max_turns + 1):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=msgs,
            tools=tools,
        )

        stop_reason = response.stop_reason

        if verbose:
            print(f"  [{agent_name}] turn {turn}: stop_reason={stop_reason}")

        # ------------------------------------------------------------
        # CASE 1: max_tokens — truncated output. Do NOT treat as done.
        # We record it and halt, surfacing the truncation to the caller
        # rather than silently returning a cut-off answer as if it were
        # a real final response.
        # ------------------------------------------------------------
        if stop_reason == "max_tokens":
            truncated = True
            partial_text = _extract_text(response)
            msgs.append({"role": "assistant", "content": response.content})
            return LoopResult(
                final_text=partial_text,
                stop_reason=stop_reason,
                turns_used=turn,
                halted_cleanly=False,
                truncated=True,
                tool_calls_made=tool_calls_made,
                transcript=msgs,
                error=(
                    f"[{agent_name}] Response was truncated at max_tokens="
                    f"{max_tokens}. Output is incomplete — increase "
                    f"max_tokens or instruct the model to be more concise."
                ),
            )

        # ------------------------------------------------------------
        # CASE 2: refusal — halt immediately, do not retry in a loop.
        # ------------------------------------------------------------
        if stop_reason == "refusal":
            msgs.append({"role": "assistant", "content": response.content})
            return LoopResult(
                final_text=_extract_text(response),
                stop_reason=stop_reason,
                turns_used=turn,
                halted_cleanly=False,
                truncated=False,
                tool_calls_made=tool_calls_made,
                transcript=msgs,
                error=f"[{agent_name}] Model refused to continue.",
            )

        # ------------------------------------------------------------
        # CASE 3: pause_turn — long-running server-side tool use (e.g.
        # web search). Correct handling: send the conversation back
        # unchanged so the model can continue. This is NOT a local
        # tool-execution step and NOT a halt.
        # ------------------------------------------------------------
        if stop_reason == "pause_turn":
            msgs.append({"role": "assistant", "content": response.content})
            continue  # loop again with the same msgs, Claude resumes

        # ------------------------------------------------------------
        # CASE 4: tool_use — Claude wants to act. Execute every
        # requested tool call, append results, loop again.
        # ------------------------------------------------------------
        if stop_reason == "tool_use":
            msgs.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_calls_made.append(
                    {"turn": turn, "name": block.name, "input": block.input}
                )
                if verbose:
                    print(
                        f"    -> calling tool '{block.name}' "
                        f"with input={json.dumps(block.input)[:200]}"
                    )

                try:
                    result_text = tool_executor(block.name, block.input)
                    is_error = False
                except Exception as exc:  # tool execution failure
                    result_text = f"Tool error: {exc}"
                    is_error = True

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                        "is_error": is_error,
                    }
                )

            msgs.append({"role": "user", "content": tool_results})
            continue  # loop again so Claude sees the tool results

        # ------------------------------------------------------------
        # CASE 5: end_turn / stop_sequence — clean halt.
        # ------------------------------------------------------------
        if stop_reason in ("end_turn", "stop_sequence"):
            msgs.append({"role": "assistant", "content": response.content})
            return LoopResult(
                final_text=_extract_text(response),
                stop_reason=stop_reason,
                turns_used=turn,
                halted_cleanly=True,
                truncated=False,
                tool_calls_made=tool_calls_made,
                transcript=msgs,
            )

        # ------------------------------------------------------------
        # CASE 6: anything unrecognized — fail loudly rather than
        # guessing. New stop_reason values may be added over time;
        # silently falling through would be worse than erroring.
        # ------------------------------------------------------------
        raise RuntimeError(
            f"[{agent_name}] Unhandled stop_reason: {stop_reason!r}. "
            f"Refusing to guess whether this means halt or continue."
        )

    # ------------------------------------------------------------
    # Safety valve: ran out of turns without a clean halt.
    # ------------------------------------------------------------
    raise MaxTurnsExceeded(
        f"[{agent_name}] Exceeded max_turns={max_turns} without reaching "
        f"end_turn. Last stop_reason={stop_reason!r}. This usually means "
        f"the model is stuck retrying a failing tool, or max_turns is set "
        f"too low for the task complexity."
    )


def _extract_text(response: anthropic.types.Message) -> str:
    """Concatenate all text blocks in a response into a single string."""
    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
