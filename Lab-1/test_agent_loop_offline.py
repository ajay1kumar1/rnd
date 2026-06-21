"""
test_agent_loop_offline.py

Offline validation of agent_loop.run_agent_loop's stop_reason state
machine, using a hand-built mock client (no network access, no API key
required). This is what we can actually execute in this sandbox to prove
the loop logic is correct; main.py is the real, API-backed end-to-end demo
to run in an environment with ANTHROPIC_API_KEY set.

Covers:
  - tool_use -> tool_use -> end_turn (normal multi-turn loop)
  - max_tokens (must NOT be treated as a clean halt)
  - pause_turn (must continue without local tool execution)
  - refusal (must halt immediately)
  - unrecognized stop_reason (must raise, not silently continue)
  - max_turns safety ceiling (must raise MaxTurnsExceeded)
  - DocumentPipeline ordering enforcement (analysis never runs if
    extraction's result object is marked failed)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from agent_loop import run_agent_loop, MaxTurnsExceeded


# ==========================================================================
# Mock Anthropic client -- scripted sequence of responses, one per call.
# ==========================================================================

class MockBlock:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockMessage:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class ScriptedClient:
    """client.messages.create(...) returns the next item in `script`,
    in order, regardless of arguments (sufficient for unit-testing the
    loop's branching logic in isolation)."""

    def __init__(self, script: list[MockMessage]):
        self._script = list(script)
        self._calls = 0
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        if self._calls >= len(self._script):
            raise AssertionError("ScriptedClient ran out of scripted responses")
        msg = self._script[self._calls]
        self._calls += 1
        return msg


def text_block(t):
    return MockBlock("text", text=t)


def tool_use_block(id_, name, input_):
    return MockBlock("tool_use", id=id_, name=name, input=input_)


# ==========================================================================
# TESTS
# ==========================================================================

def test_normal_multiturn_tool_loop():
    """tool_use -> tool_use -> end_turn should execute 2 tools and halt cleanly."""
    script = [
        MockMessage([tool_use_block("t1", "search", {"q": "foo"})], "tool_use"),
        MockMessage([tool_use_block("t2", "save", {"fact": "bar"})], "tool_use"),
        MockMessage([text_block("Done. Found bar.")], "end_turn"),
    ]
    client = ScriptedClient(script)

    calls = []
    def executor(name, inp):
        calls.append((name, inp))
        return f"result for {name}"

    result = run_agent_loop(
        client, model="x", system="sys",
        messages=[{"role": "user", "content": "go"}],
        tools=[], tool_executor=executor, max_turns=5, verbose=False,
        agent_name="test",
    )

    assert result.halted_cleanly is True, "expected clean halt on end_turn"
    assert result.stop_reason == "end_turn"
    assert result.truncated is False
    assert result.final_text == "Done. Found bar."
    assert len(calls) == 2, f"expected 2 tool calls, got {len(calls)}"
    assert calls[0][0] == "search" and calls[1][0] == "save"
    print("PASS: test_normal_multiturn_tool_loop")


def test_max_tokens_not_treated_as_done():
    """max_tokens must be flagged truncated=True, halted_cleanly=False,
    and must carry an error -- it must NOT look identical to a real finish."""
    script = [
        MockMessage([text_block("This response got cut off mid-sent")], "max_tokens"),
    ]
    client = ScriptedClient(script)

    result = run_agent_loop(
        client, model="x", system="sys",
        messages=[{"role": "user", "content": "go"}],
        tools=[], tool_executor=lambda n, i: "", max_turns=5, verbose=False,
        agent_name="test",
    )

    assert result.stop_reason == "max_tokens"
    assert result.truncated is True
    assert result.halted_cleanly is False
    assert result.error is not None, "max_tokens must surface a non-None error"
    print("PASS: test_max_tokens_not_treated_as_done")


def test_pause_turn_continues_without_local_tool_exec():
    """pause_turn should NOT trigger the tool_executor and should resume
    the loop, eventually reaching end_turn."""
    script = [
        MockMessage([text_block("(thinking, long-running search...)")], "pause_turn"),
        MockMessage([text_block("Here is the final answer.")], "end_turn"),
    ]
    client = ScriptedClient(script)

    exec_calls = []
    def executor(name, inp):
        exec_calls.append(name)
        return "should not be called"

    result = run_agent_loop(
        client, model="x", system="sys",
        messages=[{"role": "user", "content": "go"}],
        tools=[], tool_executor=executor, max_turns=5, verbose=False,
        agent_name="test",
    )

    assert exec_calls == [], "tool_executor must NOT be invoked for pause_turn"
    assert result.stop_reason == "end_turn"
    assert result.halted_cleanly is True
    assert result.turns_used == 2
    print("PASS: test_pause_turn_continues_without_local_tool_exec")


def test_refusal_halts_immediately():
    script = [
        MockMessage([text_block("I can't help with that.")], "refusal"),
    ]
    client = ScriptedClient(script)

    result = run_agent_loop(
        client, model="x", system="sys",
        messages=[{"role": "user", "content": "go"}],
        tools=[], tool_executor=lambda n, i: "", max_turns=5, verbose=False,
        agent_name="test",
    )

    assert result.stop_reason == "refusal"
    assert result.halted_cleanly is False
    assert result.error is not None
    print("PASS: test_refusal_halts_immediately")


def test_unrecognized_stop_reason_raises():
    script = [
        MockMessage([text_block("???")], "some_future_stop_reason"),
    ]
    client = ScriptedClient(script)

    try:
        run_agent_loop(
            client, model="x", system="sys",
            messages=[{"role": "user", "content": "go"}],
            tools=[], tool_executor=lambda n, i: "", max_turns=5, verbose=False,
            agent_name="test",
        )
        raise AssertionError("expected RuntimeError for unrecognized stop_reason")
    except RuntimeError as e:
        assert "Unhandled stop_reason" in str(e)
        print("PASS: test_unrecognized_stop_reason_raises")


def test_max_turns_safety_ceiling():
    """A model stuck forever in tool_use should trip MaxTurnsExceeded
    rather than loop indefinitely."""
    script = [
        MockMessage([tool_use_block(f"t{i}", "retry_tool", {})], "tool_use")
        for i in range(10)
    ]
    client = ScriptedClient(script)

    try:
        run_agent_loop(
            client, model="x", system="sys",
            messages=[{"role": "user", "content": "go"}],
            tools=[], tool_executor=lambda n, i: "still failing",
            max_turns=3, verbose=False, agent_name="test",
        )
        raise AssertionError("expected MaxTurnsExceeded")
    except MaxTurnsExceeded as e:
        assert "max_turns=3" in str(e)
        print("PASS: test_max_turns_safety_ceiling")


def test_pipeline_order_enforcement():
    """DocumentPipeline must never invoke analysis if extraction's
    SubagentResult is success=False -- structurally, not just by luck."""
    from subagents import SubagentResult
    from orchestrator import DocumentPipeline, PipelineOrderError

    # Build a DocumentPipeline-like object without hitting the network:
    # we only need to test _analyze's defensive gate, which requires no
    # client calls when the input has already failed.
    class DummyClient:
        pass

    pipeline = DocumentPipeline.__new__(DocumentPipeline)  # skip __init__
    pipeline.client = DummyClient()
    pipeline.extractor = None
    pipeline.analyzer = None
    pipeline.validator = None

    failed_extraction = SubagentResult(
        agent_name="ExtractorAgent", success=False, output=None,
        raw_text="", error="extraction blew up",
    )

    try:
        pipeline._analyze(failed_extraction)
        raise AssertionError("expected PipelineOrderError")
    except PipelineOrderError:
        print("PASS: test_pipeline_order_enforcement (analysis correctly blocked)")


def test_tool_registry_extraction_then_analysis_data_flow():
    """Validate the deterministic tool functions (no LLM involved) compose
    correctly: extract_document's output is valid input to analyze_content,
    whose output is valid input to validate_output, and that validation
    correctly flags a document missing a title/parties."""
    import tools as T

    good_doc = (
        "Master Services Agreement\n"
        "Date: 2026-03-15\n"
        "Parties: Acme Corp, Globex Inc\n"
        "Clause 1: Either party may terminate this agreement with 30 days notice.\n"
        "Clause 2: Liability under this agreement is capped at total fees paid.\n"
    )
    extracted = json.loads(T.tool_extract_document({"raw_text": good_doc}))
    assert extracted["title"] == "Master Services Agreement"
    assert extracted["parties"] == ["Acme Corp", " Globex Inc"]

    analyzed = json.loads(T.tool_analyze_content({"extracted_fields": extracted}))
    assert analyzed["clause_count"] == 2
    assert len(analyzed["risk_flags"]) == 2  # termination + liability

    validated = json.loads(T.tool_validate_output({"analysis_result": analyzed}))
    assert validated["valid"] is True, validated

    # Now a bad document: empty text should fail validation
    bad_extracted = json.loads(T.tool_extract_document({"raw_text": "   \n  "}))
    bad_analyzed = json.loads(T.tool_analyze_content({"extracted_fields": bad_extracted}))
    bad_validated = json.loads(T.tool_validate_output({"analysis_result": bad_analyzed}))
    assert bad_validated["valid"] is False
    assert len(bad_validated["errors"]) >= 1

    print("PASS: test_tool_registry_extraction_then_analysis_data_flow")


if __name__ == "__main__":
    test_normal_multiturn_tool_loop()
    test_max_tokens_not_treated_as_done()
    test_pause_turn_continues_without_local_tool_exec()
    test_refusal_halts_immediately()
    test_unrecognized_stop_reason_raises()
    test_max_turns_safety_ceiling()
    test_pipeline_order_enforcement()
    test_tool_registry_extraction_then_analysis_data_flow()
    print("\nAll offline tests passed.")
