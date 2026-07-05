import json
from anthropic import Anthropic

# Weak tools with vague descriptions and minimal guidance
WEAK_TOOLS = [
    {
        "name": "search",
        "description": "Search for something",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "lookup",
        "description": "Look up information",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The ID to look up"
                }
            },
            "required": ["id"]
        }
    },
    {
        "name": "check_status",
        "description": "Check the status of something",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Reference number or identifier"
                }
            },
            "required": ["reference"]
        }
    }
]

# Strong tools with specific names, detailed descriptions, and precise schemas
STRONG_TOOLS = [
    {
        "name": "search_products",
        "description": (
            "Searches the NorthPeak product CATALOG by free-text query. Use this to find "
            "product availability, pricing, or whether a specific product exists in inventory. "
            "Do NOT use this to check something a customer already bought — for an existing "
            "purchase use get_order_status instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text product query (e.g. 'wireless noise-cancelling headphones')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of products to return",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_order_status",
        "description": (
            "Retrieves the status of an EXISTING customer order by order ID, including shipping "
            "status, items ordered, and tracking information. Use this whenever a customer "
            "provides an order number or asks about a purchase they already made. "
            "Do NOT use this to browse the catalog — for products use search_products instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The NorthPeak order ID in the format 'NP-XXXXXX' (e.g. 'NP-123456')",
                    "pattern": "^NP-[0-9]{6}$"
                }
            },
            "required": ["order_id"]
        }
    }
]

# Test cases: product searches and order status queries
TEST_CASES = [
    "Find wireless headphones with active noise cancellation",
    "What is the status of my order #ORD-2024-089234?",
    "Search for gaming laptops under $2000",
    "Check tracking for order ID #SHIP-2024-001567",
    "I need a 4K monitor 27 inches for video editing",
    "Can you look up the status of order #12345?",
    "Find USB-C charging cables rated for 100W power delivery",
    "What's the current shipping status for order ORD-2024-056789?"
]


def score_tool_routing():
    """
    Evaluate tool routing using Anthropic's tool_choice={"type":"any"}.
    Tests how well the weak tools are selected for various queries.
    """
    client = Anthropic()
    results = []

    print("=" * 70)
    print("WEAK TOOL ROUTING EVALUATION")
    print("=" * 70)
    print()

    for i, test_query in enumerate(TEST_CASES, 1):
        print(f"Test Case {i}: {test_query}")
        print("-" * 70)

        # Call Claude with tool_choice={"type": "any"}
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            tools=WEAK_TOOLS,
            tool_choice={"type": "any"},
            messages=[
                {
                    "role": "user",
                    "content": test_query
                }
            ]
        )

        # Extract tool usage
        tool_used = None
        tool_input = None

        for block in response.content:
            if hasattr(block, 'type') and block.type == "tool_use":
                tool_used = block.name
                tool_input = block.input
                break

        # Categorize the query
        is_search = any(word in test_query.lower() for word in ["find", "search", "look for", "want", "need"])
        is_order_status = any(word in test_query.lower() for word in ["order", "status", "tracking", "shipping"])

        expected_tool = "search" if is_search else "check_status" if is_order_status else None

        result = {
            "query": test_query,
            "tool_used": tool_used,
            "tool_input": tool_input,
            "expected_tool": expected_tool,
            "match": tool_used == expected_tool if expected_tool else None
        }

        results.append(result)

        print(f"  Tool Used: {tool_used}")
        print(f"  Expected: {expected_tool}")
        print(f"  Match: {'✓' if result['match'] else '✗' if result['match'] is not None else '?'}")
        if tool_input:
            print(f"  Input: {json.dumps(tool_input, indent=4)}")
        print()

    # Summary statistics
    print("=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)

    total_tests = len(results)
    matched = sum(1 for r in results if r['match'] is True)
    unmatched = sum(1 for r in results if r['match'] is False)
    accuracy = (matched / total_tests * 100) if total_tests > 0 else 0

    print(f"Total Tests: {total_tests}")
    print(f"Correct Routing: {matched}")
    print(f"Incorrect Routing: {unmatched}")
    print(f"Accuracy: {accuracy:.1f}%")
    print()

    # Tool usage breakdown
    print("Tool Usage Breakdown:")
    tool_counts = {}
    for r in results:
        if r['tool_used']:
            tool_counts[r['tool_used']] = tool_counts.get(r['tool_used'], 0) + 1

    for tool, count in sorted(tool_counts.items()):
        print(f"  {tool}: {count} times")

    print()
    return results


def main():
    """Run the weak tools evaluation."""
    print("\nStarting weak tools evaluation...\n")

    try:
        results = score_tool_routing()
        print("Evaluation complete!")
        print("\nKey Observation:")
        print("  Weak tools with vague descriptions often lead to suboptimal")
        print("  tool selection. The model must infer intent from minimal context.")

    except Exception as e:
        print(f"Error during evaluation: {e}")
        raise


if __name__ == "__main__":
    main()
