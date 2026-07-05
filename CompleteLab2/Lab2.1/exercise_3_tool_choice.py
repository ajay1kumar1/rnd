import json
from anthropic import Anthropic

client = Anthropic()
MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

CLASSIFY_TOOL = {
    "name": "classify_ticket",
    "description": (
        "Classify an incoming customer support ticket into exactly one category. "
        "Always call this before drafting any reply so the right team is routed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["order_issue", "product_question", "return_request", "other"],
                "description": (
                    "order_issue – shipping delays, missing items, wrong order; "
                    "product_question – specs, compatibility, availability; "
                    "return_request – customer wants to return or exchange; "
                    "other – anything that does not fit the above."
                ),
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Confidence level in the chosen category.",
            },
            "reason": {
                "type": "string",
                "description": "One-sentence justification for the chosen category.",
            },
        },
        "required": ["category", "confidence", "reason"],
    },
}

DRAFT_REPLY_TOOL = {
    "name": "draft_customer_reply",
    "description": (
        "Draft a professional, empathetic reply to a customer support ticket. "
        "Call this after classify_ticket so the tone and content match the category."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Email subject line for the reply.",
            },
            "body": {
                "type": "string",
                "description": "Full body of the customer reply (plain text, 2–4 sentences).",
            },
            "tone": {
                "type": "string",
                "enum": ["apologetic", "informative", "friendly"],
                "description": (
                    "apologetic – for order issues or delays; "
                    "informative – for product questions; "
                    "friendly – for returns or neutral enquiries."
                ),
            },
        },
        "required": ["subject", "body", "tone"],
    },
}

TOOLS = [CLASSIFY_TOOL, DRAFT_REPLY_TOOL]

modes = {
    "auto":   {"type": "auto"},
    "any":    {"type": "any"},
    "FORCED": {"type": "tool", "name": "classify_ticket"},
}

# ---------------------------------------------------------------------------
# Sample tickets (one per category)
# ---------------------------------------------------------------------------

TICKETS = [
    {
        "id":      "T-001",
        "subject": "Order still not arrived",
        "body":    "Hi, I placed order NP-000002 three weeks ago and it still hasn't arrived. "
                   "The tracking page just says 'in transit'. What is going on?",
        "expected_category": "order_issue",
    },
    {
        "id":      "T-002",
        "subject": "Monitor compatibility question",
        "body":    "Does the NorthPeak 27\" 4K Monitor support DisplayPort 1.4? "
                   "I need to drive it at 144 Hz from my GPU.",
        "expected_category": "product_question",
    },
    {
        "id":      "T-003",
        "subject": "Return my keyboard please",
        "body":    "I received my NorthPeak Mechanical Keyboard yesterday but the key-travel "
                   "is much stiffer than I expected. I'd like to return it for a full refund.",
        "expected_category": "return_request",
    },
    {
        "id":      "T-004",
        "subject": "Bulk order pricing",
        "body":    "We are a mid-sized company looking to kit out 40 desks. "
                   "Do you offer corporate or volume-discount pricing?",
        "expected_category": "other",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_tool_calls(content) -> list[dict]:
    """Return a list of {name, input} dicts for every tool_use block in content."""
    return [
        {"name": block.name, "input": block.input}
        for block in content
        if hasattr(block, "type") and block.type == "tool_use"
    ]


def _print_ticket(ticket: dict) -> None:
    print(f"  Ticket {ticket['id']}: {ticket['subject']}")
    print(f"  Body   : {ticket['body'][:80]}…")
    print(f"  Expected category: {ticket['expected_category']}")


# ---------------------------------------------------------------------------
# Demo 1 — tool_choice "auto"
#   Claude decides freely whether to call a tool at all.
#   For clear support tickets it will almost always classify;
#   for a simple greeting it might just reply in text.
# ---------------------------------------------------------------------------

def demo_auto(ticket: dict) -> None:
    print("\n[MODE: auto]  Claude chooses whether to call a tool.")
    _print_ticket(ticket)

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        tools=TOOLS,
        tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": ticket["body"]}],
    )

    calls = _extract_tool_calls(response.content)
    if calls:
        for call in calls:
            print(f"  → Tool called : {call['name']}")
            print(f"    Input       : {json.dumps(call['input'], indent=6)}")
    else:
        text = next(
            (b.text for b in response.content if hasattr(b, "text")), "(no text)"
        )
        print(f"  → No tool called. Text response: {text[:120]}")


# ---------------------------------------------------------------------------
# Demo 2 — tool_choice "any"
#   Claude MUST call at least one tool; it picks which one.
# ---------------------------------------------------------------------------

def demo_any(ticket: dict) -> None:
    print("\n[MODE: any]  Claude must call at least one tool (its choice).")
    _print_ticket(ticket)

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        tools=TOOLS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": ticket["body"]}],
    )

    for call in _extract_tool_calls(response.content):
        print(f"  → Tool called : {call['name']}")
        print(f"    Input       : {json.dumps(call['input'], indent=6)}")


# ---------------------------------------------------------------------------
# Demo 3 — tool_choice {"type": "tool", "name": "classify_ticket"}
#   Forces exactly classify_ticket regardless of what Claude might prefer.
# ---------------------------------------------------------------------------

def demo_forced_classify(ticket: dict) -> None:
    print("\n[MODE: tool=classify_ticket]  Forced — must call classify_ticket.")
    _print_ticket(ticket)

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        tools=TOOLS,
        tool_choice={"type": "tool", "name": "classify_ticket"},
        messages=[{"role": "user", "content": ticket["body"]}],
    )

    for call in _extract_tool_calls(response.content):
        category = call["input"].get("category", "MISSING")
        matched  = category == ticket["expected_category"]
        print(f"  → category   : {category}  {'✓' if matched else '✗ expected ' + ticket['expected_category']}")
        print(f"    confidence : {call['input'].get('confidence')}")
        print(f"    reason     : {call['input'].get('reason')}")


# ---------------------------------------------------------------------------
# Demo 4 — enum enforcement
#   Demonstrates that the JSON Schema enum prevents invalid categories.
#   We send a deliberately ambiguous ticket and inspect that the returned
#   category is always one of the four valid values — never a free-form string.
# ---------------------------------------------------------------------------

def demo_enum_enforcement() -> None:
    print("\n[ENUM ENFORCEMENT]  Schema enum constrains output to valid categories.")
    print("  Sending five tickets; verifying every returned category is in the enum.")

    valid_categories = {
        opt
        for prop in [CLASSIFY_TOOL["input_schema"]["properties"]["category"]]
        for opt in prop["enum"]
    }
    print(f"  Valid values: {sorted(valid_categories)}")

    edge_cases = [
        "I hate your website, it is so hard to navigate.",
        "Can I change the delivery address for NP-000001?",
        "Do you ship internationally?",
        "The webcam lens cap is missing from my box.",
        "I want to exchange my mouse for a different colour.",
    ]

    all_valid = True
    for msg in edge_cases:
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            tools=[CLASSIFY_TOOL],
            tool_choice={"type": "tool", "name": "classify_ticket"},
            messages=[{"role": "user", "content": msg}],
        )
        calls = _extract_tool_calls(response.content)
        category = calls[0]["input"].get("category", "MISSING") if calls else "NO_CALL"
        valid    = category in valid_categories
        all_valid = all_valid and valid
        mark     = "✓" if valid else "✗ INVALID"
        print(f"  {mark}  '{msg[:55]}…'  →  {category}")

    print(f"\n  Result: {'All categories valid — enum enforcement works.' if all_valid else 'ENUM VIOLATION DETECTED.'}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("TOOL-CHOICE MODE DEMONSTRATION")
    print("=" * 70)

    # Demo 1: auto — use first ticket (order issue)
    demo_auto(TICKETS[0])

    # Demo 2: any — use second ticket (product question)
    demo_any(TICKETS[1])

    # Demo 3: forced classify — cycle through all four tickets
    print("\n" + "-" * 70)
    print("Forced classify_ticket across all four tickets:")
    for ticket in TICKETS:
        demo_forced_classify(ticket)

    # Demo 4: enum enforcement
    print("\n" + "-" * 70)
    demo_enum_enforcement()

    print("\n" + "=" * 70)
    print("Done.")


if __name__ == "__main__":
    main()
