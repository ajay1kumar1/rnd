# Module 2 — Lab 2.1: Tool Design & Error Handling

Hands-on exercises for designing Anthropic tool interfaces, handling structured service errors, and controlling tool-choice behaviour.

## Prerequisites

- Python 3.11+
- `anthropic` package (`pip install anthropic`)
- `ANTHROPIC_API_KEY` environment variable set

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Exercises

### Exercise 1 — Tool Interfaces (`exercise_1_tool_interfaces.py`)

Compares **weak** vs **strong** tool definitions and evaluates how description quality affects routing accuracy.

| Constant | Description |
|---|---|
| `WEAK_TOOLS` | Three vague tools (`search`, `lookup`, `check_status`) with minimal descriptions |
| `STRONG_TOOLS` | Two precise tools (`search_products`, `get_order_status`) with context, constraints, and negative redirects |
| `TEST_CASES` | 8 product-search and order-status queries |

**Key concepts:**
- Tool names as `object_action` (e.g. `search_products`) vs bare verbs
- Negative redirects in descriptions ("Do NOT use this for X — use Y instead")
- JSON Schema `pattern` to enforce ID formats at the schema level

```bash
python3 exercise_1_tool_interfaces.py
```

---

### Exercise 2 — Structured Errors (`exercise_2_structured_errors.py`)

Mock order service with deterministic failure injection and exponential-backoff retry logic.

| Component | Description |
|---|---|
| `ServiceError` | Exception carrying `error_type` (`not_found`, `timeout`, `server_error`), `order_id`, and `message` |
| `inject_failure()` | Register a deterministic outcome for any order ID before a test runs |
| `orders_service()` | Returns order data or raises `ServiceError` based on `_FAILURE_MAP` |
| `call_order_tool()` | Normalises results to `{"isError": bool, "isRetryable": bool, ...}` |
| `run_with_retry()` | Retries transient errors with exponential backoff (start 0.2 s, doubles each attempt) |

**Pre-registered order IDs:**

| ID | Outcome |
|---|---|
| `NP-000001` … `NP-000003` | success |
| `NP-404001`, `NP-404002` | `NOT_FOUND` (permanent) |
| `NP-408001`, `NP-408002` | `TIMEOUT` (retryable) |
| `NP-500001` | `SERVER_ERROR` (retryable) |

```bash
python3 exercise_2_structured_errors.py
```

---

### Exercise 3 — Tool Choice (`exercise_3_tool_choice.py`)

Demonstrates Anthropic's three `tool_choice` modes using a customer-ticket classification workflow.

| Tool | Purpose |
|---|---|
| `classify_ticket` | Classifies a ticket into a JSON Schema `enum` category |
| `draft_customer_reply` | Drafts a reply with a constrained `tone` enum |

**Category enum:** `order_issue` · `product_question` · `return_request` · `other`

| Mode key | `tool_choice` value | Behaviour |
|---|---|---|
| `"auto"` | `{"type": "auto"}` | Claude decides whether to call a tool |
| `"any"` | `{"type": "any"}` | Claude must call at least one tool |
| `"FORCED"` | `{"type": "tool", "name": "classify_ticket"}` | Exactly `classify_ticket` is called |

The `demo_enum_enforcement()` function sends five edge-case messages and asserts every returned category is one of the four valid enum values.

```bash
python3 exercise_3_tool_choice.py
```
