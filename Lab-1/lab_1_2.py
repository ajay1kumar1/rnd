"""
Lab 1.2 — Controlling Execution: Hooks, Decomposition & Session State (Optional)

Three independent demos, run via CLI flag:

  1. hooks       -> PostToolUse hook that autoflags/blocks writes to a protected directory
  2. decompose    -> fixed 3-step invoice flow vs. adaptively-branching support triage
  3. session      -> resume a session and fork it to explore two solution paths

Usage:
    python lab_1_2.py hooks
    python lab_1_2.py decompose --mode fixed
    python lab_1_2.py decompose --mode adaptive
    python lab_1_2.py session
"""

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookMatcher,
    TextBlock,
)

load_dotenv()
assert os.environ.get("ANTHROPIC_API_KEY"), "Set ANTHROPIC_API_KEY in your .env"

# Directories no tool call is allowed to write into.
PROTECTED_DIRS = ("/etc", "/system", "./config")


# ---------------------------------------------------------------------------
# 1. PostToolUse hook — log, validate, and block
# ---------------------------------------------------------------------------

async def post_tool_use_guard(input_data: dict, tool_use_id: str | None, context: HookContext) -> dict:
    """
    Runs after every tool call completes. Inspects file-write tool calls and
    flags/blocks any that touch a protected directory.

    Returning {} allows the result through unmodified.
    Returning {"hookSpecificOutput": {...}} can annotate or override behavior
    depending on what the SDK's hook contract supports for the tool in question.
    """
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {}) or {}

    if tool_name in ("Write", "Edit"):
        target_path = str(tool_input.get("file_path", ""))
        if any(target_path.startswith(p) or Path(target_path).resolve().is_relative_to(Path(p).resolve())
               for p in PROTECTED_DIRS if Path(p).exists() or p.startswith("./")):
            print(f"[HOOK] FLAGGED: '{tool_name}' touched protected path: {target_path}")
            # Example of a hard block — surface an error back to the model's
            # tool-result stream instead of silently allowing the write.
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Write to protected path '{target_path}' was blocked by policy."
                    ),
                }
            }
        else:
            print(f"[HOOK] logged: '{tool_name}' -> {target_path}")
    else:
        print(f"[HOOK] logged: tool call '{tool_name}'")

    return {}


async def run_hooks_demo():
    options = ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write", hooks=[post_tool_use_guard]),
                HookMatcher(matcher="Edit", hooks=[post_tool_use_guard]),
            ]
        },
        allowed_tools=["Write", "Edit", "Read"],
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            "Create a file called notes.txt with the text 'hello world', "
            "then try to create a file at ./config/settings.ini with some dummy content."
        )
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"[ASSISTANT] {block.text}")


# ---------------------------------------------------------------------------
# 2. Fixed vs. adaptive decomposition
# ---------------------------------------------------------------------------

FIXED_INVOICE_STEPS = [
    "Extract vendor, amount, and due date from the invoice text below.",
    "Validate the extracted amount against the PO number's approved budget.",
    "Produce a final approval/rejection summary with the extracted fields.",
]


async def run_fixed_decomposition(invoice_text: str):
    """
    Fixed decomposition: task certainty is high (we always know the steps),
    so we hardcode a 3-step pipeline and run each step as its own turn.
    """
    options = ClaudeAgentOptions(allowed_tools=[])
    async with ClaudeSDKClient(options=options) as client:
        context = invoice_text
        for i, step in enumerate(FIXED_INVOICE_STEPS, start=1):
            print(f"\n[FIXED STEP {i}/3] {step}")
            await client.query(f"{step}\n\nContext so far:\n{context}")
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"[ASSISTANT] {block.text}")
                            context += f"\n\n[Step {i} result]\n{block.text}"


async def run_adaptive_decomposition(ticket_text: str):
    """
    Adaptive decomposition: task certainty is low (we don't know up front how
    many steps a support ticket will need), so we let the model decide the
    next step after each turn, branching dynamically until it signals DONE.
    """
    options = ClaudeAgentOptions(allowed_tools=[])
    max_turns = 5
    turn = 0
    context = ticket_text

    instructions = (
        "You are triaging a support ticket adaptively. After each response, "
        "decide whether more investigation is needed. If done, end your "
        "response with the single line: DONE. Otherwise end with: NEXT: <what to check next>."
    )

    async with ClaudeSDKClient(options=options) as client:
        while turn < max_turns:
            turn += 1
            print(f"\n[ADAPTIVE TURN {turn}]")
            await client.query(f"{instructions}\n\nTicket / context:\n{context}")
            response_text = ""
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"[ASSISTANT] {block.text}")
                            response_text += block.text

            context += f"\n\n[Turn {turn} result]\n{response_text}"
            if "DONE" in response_text:
                print("[ADAPTIVE] Triage signaled completion.")
                break
        else:
            print("[ADAPTIVE] Hit max_turns without a DONE signal — escalate to a human.")


# ---------------------------------------------------------------------------
# 3. Session resume/fork with structured summaries
# ---------------------------------------------------------------------------

async def run_session_demo():
    """
    Starts a session, captures its session_id, then forks from that same
    point twice to explore two different solution paths without losing the
    original context — each fork gets its own structured summary at the end.
    """
    options = ClaudeAgentOptions(allowed_tools=[])

    # Step 1: establish the base session and do some initial work.
    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            "We need to design a caching layer for a read-heavy API. "
            "Summarize the constraints in 2 sentences before we explore options."
        )
        session_id = None
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"[BASE SESSION] {block.text}")
            # The SDK surfaces the session id on system/result messages;
            # capture it however your SDK version exposes it, e.g.:
            session_id = getattr(message, "session_id", session_id)

    if not session_id:
        print("[SESSION] Could not capture session_id — check SDK version's message shape.")
        return

    print(f"\n[SESSION] Base session id: {session_id}")

    # Step 2: fork twice from the same base session to explore two paths
    # in parallel, each with the original context intact but no cross-talk.
    fork_prompts = {
        "fork_redis": "Continuing from here: propose a Redis-based caching design. End with a structured summary: Approach / Tradeoffs / Risk.",
        "fork_cdn": "Continuing from here: propose a CDN-edge-caching design instead. End with a structured summary: Approach / Tradeoffs / Risk.",
    }

    results = {}
    for fork_name, prompt in fork_prompts.items():
        fork_options = ClaudeAgentOptions(
            allowed_tools=[],
            resume=session_id,
            fork_session=True,  # create a new branch instead of mutating the original
        )
        async with ClaudeSDKClient(options=fork_options) as client:
            await client.query(prompt)
            text = ""
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text += block.text
            print(f"\n[{fork_name.upper()}]\n{text}")
            results[fork_name] = text

    print("\n[SESSION] Both forks explored independently; base session untouched.")
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Lab 1.2 demos")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("hooks", help="PostToolUse hook demo (validate/block protected writes)")

    decompose_parser = sub.add_parser("decompose", help="Fixed vs adaptive decomposition demo")
    decompose_parser.add_argument("--mode", choices=["fixed", "adaptive"], default="fixed")

    sub.add_parser("session", help="Resume/fork session demo")

    args = parser.parse_args()

    if args.command == "hooks":
        asyncio.run(run_hooks_demo())
    elif args.command == "decompose":
        if args.mode == "fixed":
            sample_invoice = (
                "Invoice #4821 from Acme Supplies, amount $4,250.00, due 2026-07-15, PO-1190."
            )
            asyncio.run(run_fixed_decomposition(sample_invoice))
        else:
            sample_ticket = (
                "Customer reports intermittent 502 errors on checkout since this morning. "
                "No recent deploys reported by the customer."
            )
            asyncio.run(run_adaptive_decomposition(sample_ticket))
    elif args.command == "session":
        asyncio.run(run_session_demo())


if __name__ == "__main__":
    main()
