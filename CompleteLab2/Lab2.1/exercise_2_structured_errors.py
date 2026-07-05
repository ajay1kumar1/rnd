import os
import time
from enum import Enum
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class ErrorType(str, Enum):
    NOT_FOUND = "not_found"
    TIMEOUT   = "timeout"
    SERVER    = "server_error"


class ServiceError(Exception):
    """Raised by orders_service when a call cannot be fulfilled."""

    def __init__(self, error_type: ErrorType, order_id: str, message: str):
        super().__init__(message)
        self.error_type = error_type
        self.order_id   = order_id
        self.message    = message

    def to_dict(self) -> dict:
        return {
            "error":    self.error_type.value,
            "order_id": self.order_id,
            "message":  self.message,
        }


# ---------------------------------------------------------------------------
# Failure-injection registry
# ---------------------------------------------------------------------------
# Maps order_id → ErrorType (or None for success).
# Deterministic: same id always produces the same outcome.
_FAILURE_MAP: dict[str, ErrorType | None] = {
    "NP-000001": None,                  # success
    "NP-000002": None,                  # success
    "NP-000003": None,                  # success
    "NP-500001": ErrorType.SERVER,      # server error
    "NP-408001": ErrorType.TIMEOUT,     # timeout
    "NP-408002": ErrorType.TIMEOUT,     # timeout
    "NP-404001": ErrorType.NOT_FOUND,   # not found
    "NP-404002": ErrorType.NOT_FOUND,   # not found
}

# Mock order data returned for successful lookups
_ORDER_DATA: dict[str, dict] = {
    "NP-000001": {
        "order_id":       "NP-000001",
        "status":         "shipped",
        "tracking":       "1Z999AA10123456784",
        "items":          [{"sku": "HDX-200", "name": "NorthPeak HD Webcam", "qty": 1}],
        "estimated_delivery": "2026-07-08",
    },
    "NP-000002": {
        "order_id":       "NP-000002",
        "status":         "processing",
        "tracking":       None,
        "items":          [
            {"sku": "KBD-550", "name": "NorthPeak Mechanical Keyboard", "qty": 1},
            {"sku": "MSE-110", "name": "NorthPeak Wireless Mouse",      "qty": 1},
        ],
        "estimated_delivery": "2026-07-10",
    },
    "NP-000003": {
        "order_id":       "NP-000003",
        "status":         "delivered",
        "tracking":       "1Z999AA10123456000",
        "items":          [{"sku": "MON-4K27", "name": "NorthPeak 27\" 4K Monitor", "qty": 2}],
        "estimated_delivery": "2026-07-02",
    },
}


def inject_failure(order_id: str, outcome: ErrorType | None) -> None:
    """
    Register a deterministic outcome for *order_id*.

    Pass outcome=None to make the id succeed (registers mock data too
    if not already present). Pass an ErrorType to make it fail.
    """
    _FAILURE_MAP[order_id] = outcome
    if outcome is None and order_id not in _ORDER_DATA:
        # Provide minimal placeholder data so the id is actually serveable.
        _ORDER_DATA[order_id] = {
            "order_id": order_id,
            "status":   "processing",
            "tracking": None,
            "items":    [],
            "estimated_delivery": None,
        }


# ---------------------------------------------------------------------------
# Mock service
# ---------------------------------------------------------------------------

def orders_service(order_id: str) -> dict:
    """
    Return order data for *order_id*, or raise ServiceError.

    Outcomes are driven entirely by _FAILURE_MAP — call inject_failure()
    beforehand to control behaviour in tests.
    """
    if order_id not in _FAILURE_MAP:
        raise ServiceError(
            ErrorType.NOT_FOUND,
            order_id,
            f"Order {order_id!r} does not exist.",
        )

    outcome = _FAILURE_MAP[order_id]

    if outcome is ErrorType.TIMEOUT:
        raise ServiceError(
            ErrorType.TIMEOUT,
            order_id,
            f"Request for order {order_id!r} timed out. Please try again.",
        )

    if outcome is ErrorType.SERVER:
        raise ServiceError(
            ErrorType.SERVER,
            order_id,
            f"Internal server error while retrieving order {order_id!r}.",
        )

    if outcome is ErrorType.NOT_FOUND:
        raise ServiceError(
            ErrorType.NOT_FOUND,
            order_id,
            f"Order {order_id!r} was not found.",
        )

    # outcome is None → success
    return _ORDER_DATA[order_id]


# ---------------------------------------------------------------------------
# Claude integration helpers
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_order_status",
        "description": (
            "Retrieves the status of an EXISTING NorthPeak order by order ID, "
            "including shipping status, items, and tracking information. "
            "Do NOT use this to browse the catalog — for products use search_products instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "NorthPeak order ID in the format 'NP-XXXXXX'",
                    "pattern": "^NP-[0-9]{6}$",
                }
            },
            "required": ["order_id"],
        },
    }
]


def handle_tool_call(order_id: str) -> dict:
    """Call orders_service and return a structured result dict for Claude."""
    try:
        data = orders_service(order_id)
        return {"success": True, "data": data}
    except ServiceError as exc:
        return {"success": False, **exc.to_dict()}


# TIMEOUT and SERVER errors are transient — worth retrying.
# NOT_FOUND is permanent — retrying will never help.
_RETRYABLE = {ErrorType.TIMEOUT, ErrorType.SERVER}


def call_order_tool(order_id: str) -> dict:
    """
    Thin wrapper around orders_service that normalises the result into a
    shape suitable for run_with_retry:

      On success:  {"isError": False, "isRetryable": False, "data": {...}}
      On failure:  {"isError": True,  "isRetryable": bool,  "error": str,
                    "order_id": str,  "message": str}
    """
    try:
        data = orders_service(order_id)
        return {"isError": False, "isRetryable": False, "data": data}
    except ServiceError as exc:
        return {
            "isError":     True,
            "isRetryable": exc.error_type in _RETRYABLE,
            **exc.to_dict(),
        }


def run_with_retry(order_id: str, max_attempts: int = 4) -> dict:
    """
    Call call_order_tool up to *max_attempts* times with exponential backoff.

    Returns the first successful result, or the final error result if all
    retryable attempts are exhausted or the error is permanent.
    """
    delay = 0.2
    for attempt in range(1, max_attempts + 1):
        result = call_order_tool(order_id)

        if not result["isError"]:
            return result                               # success — done

        if result["isRetryable"] and attempt < max_attempts:
            print(f"  [retry] attempt {attempt} failed ({result['error']}), "
                  f"retrying in {delay:.2f}s …")
            time.sleep(delay)
            delay *= 2
            continue

        return result                                   # permanent error or exhausted


def run_conversation(user_message: str) -> str:
    """Single-turn agentic loop: let Claude call get_order_status once."""
    client = Anthropic()
    messages = [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        tools=TOOLS,
        messages=messages,
    )

    # If Claude chose to call a tool, execute it and get a final reply.
    if response.stop_reason == "tool_use":
        tool_use_block = next(b for b in response.content if b.type == "tool_use")
        order_id       = tool_use_block.input["order_id"]
        tool_result    = handle_tool_call(order_id)

        messages += [
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [
                    {
                        "type":        "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content":     str(tool_result),
                    }
                ],
            },
        ]

        final = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )
        return final.content[0].text

    return response.content[0].text


# ---------------------------------------------------------------------------
# Main: demonstrate each failure mode
# ---------------------------------------------------------------------------

TEST_SCENARIOS = [
    ("NP-000001", "What is the status of my order NP-000001?"),
    ("NP-404001", "Can you check order NP-404001 for me?"),
    ("NP-408001", "Where is my order NP-408001?"),
    ("NP-500001", "Give me an update on order NP-500001."),
]


def main():
    print("=" * 70)
    print("STRUCTURED ERROR HANDLING DEMO")
    print("=" * 70)

    for order_id, query in TEST_SCENARIOS:
        outcome = _FAILURE_MAP.get(order_id, "unknown")
        label   = outcome.value if isinstance(outcome, ErrorType) else "success"

        print(f"\nScenario [{label.upper()}]  order_id={order_id}")
        print(f"  User: {query}")
        print("-" * 70)

        reply = run_conversation(query)
        print(f"  Claude: {reply}")

    print("\n" + "=" * 70)
    print("Demo complete.")


if __name__ == "__main__":
    main()
