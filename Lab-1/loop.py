"""
loop.py

Implements the agentic tool-use loop exactly as specified:

  1. Import Anthropic SDK + classify_ticket. Initialise client.
  2. Define tools list with classify_ticket schema (ticket_text + fields_needed, both required).
  3. Build initial messages with one user-role entry prompting full classification.
  4. while True loop — call API, print iteration + stop_reason each turn.
  5. Append assistant response to messages FIRST, before any branching.
  6. end_turn  -> print final text, break.
  7. tool_use  -> find tool_use blocks, call function with block.input,
                  collect tool_result messages, append as single user turn, continue.
"""

# ── Step 1: Import Anthropic SDK and classify_ticket. Initialise client. ──────

import anthropic
from tools import tool_classify_ticket as classify_ticket  # aliased to match spec name

client = anthropic.Anthropic()

# ── Step 2: Define tools list registering classify_ticket as a callable tool. ─
#    Schema declares ticket_text (string) and fields_needed (array of strings)
#    as required properties, with a clear description for each.

tools = [
    {
        "name": "classify_ticket",
        "description": (
            "Classify a support ticket and return its category, urgency, and "
            "recommended_action. Call this tool as many times as needed — "
            "use fields_needed to declare which of the three fields you are "
            "still resolving on each call, so the loop can confirm all three "
            "are populated before finishing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_text": {
                    "type": "string",
                    "description": (
                        "The raw support ticket text to classify."
                    ),
                },
                "fields_needed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of classification fields still needed, e.g. "
                        "[\"category\", \"urgency\", \"recommended_action\"]. "
                        "Pass all three on the first call; remove each field "
                        "from this list once it is confirmed."
                    ),
                },
            },
            "required": ["ticket_text", "fields_needed"],
        },
    }
]

# ── Step 3: Build initial messages — one user-role entry. ─────────────────────
#    Prompt instructs Claude to classify fully (all three fields) using the
#    tool as many times as needed until all are confirmed.

SAMPLE_TICKET = (
    "Hi, I was charged twice for my subscription last month. "
    "I need this refunded urgently — my account ref is ACC-8821."
)

messages = [
    {
        "role": "user",
        "content": (
            f"Please classify the following support ticket fully. "
            f"You must confirm all three fields — category, urgency, and "
            f"recommended_action — using the classify_ticket tool. "
            f"Call the tool as many times as needed until every field is confirmed.\n\n"
            f"Ticket:\n{SAMPLE_TICKET}"
        ),
    }
]

# ── Steps 4–7: while True loop ─────────────────────────────────────────────────

iteration = 0

while True:
    iteration += 1

    # ── Step 4: Call the API. Print iteration number and stop_reason. ──────────
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        tools=tools,
        messages=messages,
    )
    print(f"iteration={iteration}  stop_reason={response.stop_reason}")

    # ── Step 5: Append assistant response FIRST, before any branching. ─────────
    messages.append({"role": "assistant", "content": response.content})

    # ── Step 6: end_turn — print final text and break. ─────────────────────────
    if response.stop_reason == "end_turn":
        final_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        print("\nFinal response:")
        print(final_text)
        break

    # ── Step 7: tool_use — find tool_use blocks, call function, collect results,
    #            append as single user turn, continue. ──────────────────────────
    if response.stop_reason == "tool_use":
        tool_results = []

        for block in response.content:
            if block.type != "tool_use":
                continue

            # Dispatch: call the corresponding Python function with block.input
            if block.name == "classify_ticket":
                result = classify_ticket(block.input)
            else:
                result = f"Error: unknown tool '{block.name}'"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        # Append ALL results as a single user turn, then continue the loop
        messages.append({"role": "user", "content": tool_results})
        continue
