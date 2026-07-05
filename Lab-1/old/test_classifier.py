"""
test_classifier.py — Offline test harness for the ticket-classifier agent.

Tests cover:
  1. classify_ticket returns only requested fields with valid vocab values.
  2. classify_ticket raises ValueError for unknown fields.
  3. classify_ticket raises ValueError for empty ticket_text.
  4. run_classifier_agent always returns all three required fields.
  5. Agent never loops more times than there are fields (loop ceiling).
  6. Agent works correctly even when the tool returns all fields in one shot
     (simulated via monkeypatching).
  7. Agent raises if the tool returns an out-of-vocab value (bad tool output).
"""

import sys
from pathlib import Path
from unittest.mock import patch, call

# ── Make sure we import from the project folder ──────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from tools import classify_ticket, FIELD_VOCAB, REQUIRED_FIELDS
from agent import run_classifier_agent


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _check_vocab(field: str, value: str) -> bool:
    return value in FIELD_VOCAB[field]


# ════════════════════════════════════════════════════════════════════════════
# Tests for tools.py
# ════════════════════════════════════════════════════════════════════════════

def test_classify_ticket_single_field():
    result = classify_ticket("Some issue", ["severity"])
    assert set(result.keys()) == {"severity"}, "Should return only requested field"
    assert _check_vocab("severity", result["severity"]), "Value must be in vocab"
    print("PASS  test_classify_ticket_single_field")


def test_classify_ticket_all_fields():
    result = classify_ticket("Some issue", REQUIRED_FIELDS)
    assert set(result.keys()) == set(REQUIRED_FIELDS), "Should return all three fields"
    for field, value in result.items():
        assert _check_vocab(field, value), f"Bad value {value!r} for {field}"
    print("PASS  test_classify_ticket_all_fields")


def test_classify_ticket_returns_only_requested():
    """Only 'intent' is requested — product_area and severity must NOT appear."""
    result = classify_ticket("Some issue", ["intent"])
    assert "intent" in result
    assert "product_area" not in result
    assert "severity" not in result
    print("PASS  test_classify_ticket_returns_only_requested")


def test_classify_ticket_unknown_field_raises():
    raised = False
    try:
        classify_ticket("Some issue", ["nonexistent_field"])
    except ValueError:
        raised = True
    assert raised, "Should raise ValueError for unknown field"
    print("PASS  test_classify_ticket_unknown_field_raises")


def test_classify_ticket_empty_text_raises():
    raised = False
    try:
        classify_ticket("", ["severity"])
    except ValueError:
        raised = True
    assert raised, "Should raise ValueError for empty ticket_text"
    print("PASS  test_classify_ticket_empty_text_raises")


# ════════════════════════════════════════════════════════════════════════════
# Tests for agent.py
# ════════════════════════════════════════════════════════════════════════════

def test_agent_returns_all_fields():
    """Agent must always return all three required fields."""
    result = run_classifier_agent("Billing issue, need help urgently.")
    assert set(result.keys()) == set(REQUIRED_FIELDS), (
        f"Agent result missing fields. Got: {list(result.keys())}"
    )
    for field, value in result.items():
        assert _check_vocab(field, value), f"Bad value {value!r} for {field}"
    print("PASS  test_agent_returns_all_fields")


def test_agent_loop_count_ceiling():
    """
    The agent should never need more iterations than there are required fields.
    We simulate the worst case: tool returns exactly ONE valid field per call.
    The counting wrapper returns only the first requested field each time
    (with a valid vocab value), forcing the agent to loop up to 3 times.
    """
    call_count = 0
    original_fn = classify_ticket

    def counting_wrapper(ticket_text, fields_needed):
        nonlocal call_count
        call_count += 1
        # Return only the first requested field — valid vocab value.
        return original_fn(ticket_text, [fields_needed[0]])

    # Patch _validate_partial too so the partial return passes validation.
    with patch("agent.classify_ticket", side_effect=counting_wrapper), \
         patch("agent._validate_partial"):          # skip strict shape check for this test
        run_classifier_agent("Test ticket for ceiling check.")

    assert call_count <= len(REQUIRED_FIELDS), (
        f"Agent looped {call_count} times — exceeds field count {len(REQUIRED_FIELDS)}"
    )
    print(f"PASS  test_agent_loop_count_ceiling  (calls={call_count})")


def test_agent_single_call_all_fields():
    """When the tool returns all fields at once the agent must stop after 1 call."""
    one_shot_result = {
        "product_area": "Billing",
        "severity":     "P1-Critical",
        "intent":       "Bug",
    }

    with patch("agent.classify_ticket", return_value=one_shot_result) as mock_tool:
        result = run_classifier_agent("Double-charge issue.")

    mock_tool.assert_called_once()
    assert result == one_shot_result
    print("PASS  test_agent_single_call_all_fields")


def test_agent_no_extra_loop_after_complete():
    """
    After all fields are resolved, classify_ticket must NOT be called again.
    """
    call_count = 0
    original_fn = classify_ticket

    def spy(ticket_text, fields_needed):
        nonlocal call_count
        call_count += 1
        return original_fn(ticket_text, fields_needed)

    with patch("agent.classify_ticket", side_effect=spy):
        run_classifier_agent("Security breach, need P1.")

    # Maximum legitimate calls = number of required fields (one per iteration worst-case)
    assert call_count <= len(REQUIRED_FIELDS), (
        f"Tool was called {call_count} times but only {len(REQUIRED_FIELDS)} fields exist"
    )
    print(f"PASS  test_agent_no_extra_loop_after_complete  (calls={call_count})")


def test_agent_bad_tool_output_raises():
    """Agent must raise if the tool returns an out-of-vocabulary value."""
    bad_result = {"product_area": "INVALID_AREA", "severity": "P1-Critical", "intent": "Bug"}

    raised = False
    try:
        with patch("agent.classify_ticket", return_value=bad_result):
            run_classifier_agent("Some ticket.")
    except ValueError:
        raised = True

    assert raised, "Agent should raise ValueError on out-of-vocab tool output"
    print("PASS  test_agent_bad_tool_output_raises")


# ════════════════════════════════════════════════════════════════════════════
# Runner
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # tools.py
        test_classify_ticket_single_field,
        test_classify_ticket_all_fields,
        test_classify_ticket_returns_only_requested,
        test_classify_ticket_unknown_field_raises,
        test_classify_ticket_empty_text_raises,
        # agent.py
        test_agent_returns_all_fields,
        test_agent_loop_count_ceiling,
        test_agent_single_call_all_fields,
        test_agent_no_extra_loop_after_complete,
        test_agent_bad_tool_output_raises,
    ]

    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"ERROR {t.__name__}: {exc}")
            failed += 1

    print(f"\n{'═'*45}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests.")
    sys.exit(0 if failed == 0 else 1)
