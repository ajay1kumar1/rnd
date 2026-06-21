"""
subagents.py

Specialist subagents for the hub-and-spoke pattern. Each subagent:

  1. Is a thin, self-contained wrapper around agent_loop.run_agent_loop
  2. Receives an EXPLICIT, MINIMAL context packet from the orchestrator
     (not the orchestrator's full transcript) -- this is the
     "pass explicit context into subagents" requirement from the lab.
  3. Has its own narrow tool slice and system prompt; it does not know
     about the other subagents and cannot call them. Only the orchestrator
     coordinates.
  4. Returns a typed result object so the orchestrator can branch on
     success/failure without re-parsing free text.

Two families of subagents are defined:

  Research-assistant family : ResearchSubagent
  Document-pipeline family  : ExtractorAgent, AnalyzerAgent, ValidatorAgent

Plus two general-purpose text-transform subagents used in the routing demo:
  SummarizerAgent, TranslatorAgent, ValidatorTextAgent

These do NOT call tools -- they are pure single-turn LLM calls -- but they
still go through run_agent_loop so stop_reason is still checked correctly
(no tool_use is ever requested, so the loop halts on turn 1 at end_turn).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import anthropic

from agent_loop import run_agent_loop, LoopResult
import tools as T


MODEL = "claude-sonnet-4-6"


@dataclass
class SubagentResult:
    agent_name: str
    success: bool
    output: Any
    raw_text: str
    error: Optional[str] = None
    loop_result: Optional[LoopResult] = None


# ==========================================================================
# RESEARCH SUBAGENT
# ==========================================================================

class ResearchSubagent:
    """
    Owns the search -> fetch -> save_finding tool loop for a single
    research question. Returns the findings it saved plus a written
    answer, so the orchestrator never has to inspect the raw transcript.
    """

    SYSTEM_PROMPT = (
        "You are a focused research specialist. You will be given ONE "
        "research question and nothing else -- you have no knowledge of "
        "any broader task. Your job:\n"
        "1. Use web_search to find candidate sources.\n"
        "2. Use fetch_page to read the most promising 1-2 sources.\n"
        "3. Use save_finding to record each distinct fact you want to keep, "
        "with its source URL.\n"
        "4. Once you have enough saved findings, STOP calling tools and "
        "write a concise final answer (3-6 sentences) that directly "
        "answers the question, grounded only in what you found.\n"
        "Do not call tools after you have enough information -- calling "
        "tools forever is a failure mode, not thoroughness."
    )

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def run(self, *, question: str, max_turns: int = 6) -> SubagentResult:
        T.reset_research_notebook()
        executor = T.make_executor(T.RESEARCH_TOOL_REGISTRY)

        messages = [{"role": "user", "content": f"Research question: {question}"}]

        try:
            result = run_agent_loop(
                self.client,
                model=MODEL,
                system=self.SYSTEM_PROMPT,
                messages=messages,
                tools=T.RESEARCH_TOOLS,
                tool_executor=executor,
                max_turns=max_turns,
                agent_name="ResearchSubagent",
            )
        except Exception as exc:
            return SubagentResult(
                agent_name="ResearchSubagent",
                success=False,
                output=None,
                raw_text="",
                error=str(exc),
            )

        if result.error:
            return SubagentResult(
                agent_name="ResearchSubagent",
                success=False,
                output=None,
                raw_text=result.final_text,
                error=result.error,
                loop_result=result,
            )

        return SubagentResult(
            agent_name="ResearchSubagent",
            success=True,
            output={
                "answer": result.final_text,
                "findings": T.get_research_notebook(),
            },
            raw_text=result.final_text,
            loop_result=result,
        )


# ==========================================================================
# DOCUMENT PIPELINE SUBAGENTS -- extraction / analysis / validation
# Each is intentionally single-tool-scoped: ExtractorAgent can ONLY call
# extract_document, etc. This is a second, structural layer of order
# enforcement on top of the orchestrator's programmatic gating (see
# orchestrator.py) -- even if the model tried to skip ahead, the subagent
# literally does not have the tool available to do so.
# ==========================================================================

class ExtractorAgent:
    SYSTEM_PROMPT = (
        "You are a document extraction specialist. You will be given raw "
        "document text. Call extract_document exactly once with that text, "
        "then report back the extracted fields as your final answer. Do "
        "not attempt analysis or commentary -- extraction only."
    )

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def run(self, *, raw_text: str) -> SubagentResult:
        executor = T.make_executor({"extract_document": T.tool_extract_document})
        messages = [{"role": "user", "content": f"Extract this document:\n\n{raw_text}"}]
        return _run_single_tool_subagent(
            self.client,
            agent_name="ExtractorAgent",
            system=self.SYSTEM_PROMPT,
            messages=messages,
            tool_schema=[t for t in T.PIPELINE_TOOLS if t["name"] == "extract_document"],
            executor=executor,
            extract_tool_name="extract_document",
        )


class AnalyzerAgent:
    SYSTEM_PROMPT = (
        "You are a document risk-analysis specialist. You will be given "
        "structured fields that have ALREADY been extracted from a "
        "document. Call analyze_content exactly once with those fields, "
        "then report the analysis as your final answer. You will never "
        "be given raw, unextracted text -- if the input looks like raw "
        "text rather than structured fields, say so and stop."
    )

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def run(self, *, extracted_fields: dict) -> SubagentResult:
        executor = T.make_executor({"analyze_content": T.tool_analyze_content})
        messages = [
            {
                "role": "user",
                "content": (
                    "Analyze these previously-extracted fields:\n\n"
                    f"{extracted_fields}"
                ),
            }
        ]
        return _run_single_tool_subagent(
            self.client,
            agent_name="AnalyzerAgent",
            system=self.SYSTEM_PROMPT,
            messages=messages,
            tool_schema=[t for t in T.PIPELINE_TOOLS if t["name"] == "analyze_content"],
            executor=executor,
            extract_tool_name="analyze_content",
        )


class ValidatorAgent:
    SYSTEM_PROMPT = (
        "You are a quality-validation specialist. You will be given a "
        "completed analysis result. Call validate_output exactly once with "
        "it, then report whether it passed validation as your final answer."
    )

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def run(self, *, analysis_result: dict) -> SubagentResult:
        executor = T.make_executor({"validate_output": T.tool_validate_output})
        messages = [
            {
                "role": "user",
                "content": f"Validate this analysis result:\n\n{analysis_result}",
            }
        ]
        return _run_single_tool_subagent(
            self.client,
            agent_name="ValidatorAgent",
            system=self.SYSTEM_PROMPT,
            messages=messages,
            tool_schema=[t for t in T.PIPELINE_TOOLS if t["name"] == "validate_output"],
            executor=executor,
            extract_tool_name="validate_output",
        )


def _run_single_tool_subagent(
    client, *, agent_name, system, messages, tool_schema, executor, extract_tool_name
) -> SubagentResult:
    """
    Shared plumbing for the three pipeline subagents: run the loop, then
    pull the structured JSON the underlying tool produced (not just the
    model's prose summary of it) out of the transcript so the orchestrator
    gets a reliable typed object to pass to the next stage.
    """
    try:
        result = run_agent_loop(
            client,
            model=MODEL,
            system=system,
            messages=messages,
            tools=tool_schema,
            tool_executor=executor,
            max_turns=4,
            agent_name=agent_name,
        )
    except Exception as exc:
        return SubagentResult(agent_name=agent_name, success=False, output=None, raw_text="", error=str(exc))

    if result.error:
        return SubagentResult(
            agent_name=agent_name, success=False, output=None,
            raw_text=result.final_text, error=result.error, loop_result=result,
        )

    # Pull the actual tool_result content out of the transcript -- this is
    # the ground-truth structured output, independent of how the model
    # chose to phrase its summary.
    structured_output = _find_last_tool_result(result.transcript, extract_tool_name)

    if structured_output is None:
        return SubagentResult(
            agent_name=agent_name, success=False, output=None,
            raw_text=result.final_text,
            error=f"{agent_name} never actually called {extract_tool_name}.",
            loop_result=result,
        )

    import json
    try:
        parsed = json.loads(structured_output)
    except json.JSONDecodeError:
        parsed = structured_output  # fall back to raw string

    return SubagentResult(
        agent_name=agent_name, success=True, output=parsed,
        raw_text=result.final_text, loop_result=result,
    )


def _find_last_tool_result(transcript: list[dict], tool_name: str) -> Optional[str]:
    """Walk the transcript backwards to find the most recent tool_result
    that corresponds to a call to `tool_name`."""
    # First map tool_use_id -> tool name from assistant turns
    id_to_name = {}
    for msg in transcript:
        if msg["role"] == "assistant":
            for block in msg["content"]:
                if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                    id_to_name[block.id] = block.name

    for msg in reversed(transcript):
        if msg["role"] == "user" and isinstance(msg["content"], list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    if block.get("tool_use_id") in id_to_name:
                        return block.get("content")
    return None


# ==========================================================================
# TEXT-TRANSFORM SUBAGENTS (no tools) -- used by orchestrator's routing demo
# ==========================================================================

class SummarizerAgent:
    SYSTEM_PROMPT = (
        "You are a summarization specialist. Given a block of text, "
        "produce a concise summary (3-5 sentences). Output only the "
        "summary, no preamble."
    )

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def run(self, *, text: str) -> SubagentResult:
        return _run_plain_text_subagent(
            self.client, agent_name="SummarizerAgent",
            system=self.SYSTEM_PROMPT, user_content=text,
        )


class TranslatorAgent:
    SYSTEM_PROMPT = (
        "You are a translation specialist. You will be given text and a "
        "target language. Output ONLY the translation, nothing else."
    )

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def run(self, *, text: str, target_language: str) -> SubagentResult:
        content = f"Translate the following text into {target_language}:\n\n{text}"
        return _run_plain_text_subagent(
            self.client, agent_name="TranslatorAgent",
            system=self.SYSTEM_PROMPT, user_content=content,
        )


class ValidatorTextAgent:
    SYSTEM_PROMPT = (
        "You are a validation specialist. You will be given a piece of "
        "text and a short list of requirements. Reply with 'VALID' on the "
        "first line if all requirements are met, or 'INVALID' followed by "
        "a bullet list of which requirements failed."
    )

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def run(self, *, text: str, requirements: list[str]) -> SubagentResult:
        req_block = "\n".join(f"- {r}" for r in requirements)
        content = f"Text:\n{text}\n\nRequirements:\n{req_block}"
        return _run_plain_text_subagent(
            self.client, agent_name="ValidatorTextAgent",
            system=self.SYSTEM_PROMPT, user_content=content,
        )


def _run_plain_text_subagent(client, *, agent_name, system, user_content) -> SubagentResult:
    messages = [{"role": "user", "content": user_content}]
    try:
        result = run_agent_loop(
            client, model=MODEL, system=system, messages=messages,
            tools=[], tool_executor=lambda n, i: "",
            max_turns=2, agent_name=agent_name,
        )
    except Exception as exc:
        return SubagentResult(agent_name=agent_name, success=False, output=None, raw_text="", error=str(exc))

    if result.error:
        return SubagentResult(
            agent_name=agent_name, success=False, output=None,
            raw_text=result.final_text, error=result.error, loop_result=result,
        )

    return SubagentResult(
        agent_name=agent_name, success=True, output=result.final_text,
        raw_text=result.final_text, loop_result=result,
    )
