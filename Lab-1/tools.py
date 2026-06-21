"""
tools.py

Tool schemas + execution functions used across both worked examples:

  1. Research assistant  -> web_search, fetch_page, save_finding
  2. Document pipeline    -> extract_document, analyze_content, validate_output

All tools here are deterministic MOCKS (no real network calls), so the lab
is runnable offline and reproducibly. Swap `_MOCK_*` data or the function
bodies for real implementations (requests, a real search API, etc.) when
adapting this for production.

Each tool function has signature: (tool_input: dict) -> str
and is registered in a TOOL_REGISTRY dict mapping name -> function, which
agent_loop.run_agent_loop's `tool_executor` callback dispatches through.
"""

from __future__ import annotations

import json
import time


# ==========================================================================
# RESEARCH ASSISTANT TOOLS
# ==========================================================================

RESEARCH_TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for a query and return a short list of "
            "candidate result titles + URLs + snippets. Call this when "
            "you need to discover sources, not when you already have a URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_page",
        "description": (
            "Fetch the full text content of a specific URL returned by "
            "web_search. Use this to read a source in detail before citing it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "save_finding",
        "description": (
            "Record a single verified finding (a fact plus its source URL) "
            "into the research notebook. Call this once per distinct fact "
            "you want to keep before writing your final answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string"},
                "source_url": {"type": "string"},
            },
            "required": ["fact", "source_url"],
        },
    },
]


# Small mock "index" of pages this fake search engine knows about.
_MOCK_SEARCH_INDEX = {
    "agentic loop stop_reason best practices": [
        {
            "title": "Anthropic Docs: Handling stop_reason",
            "url": "https://docs.example.com/stop-reason",
            "snippet": (
                "Explains tool_use, end_turn, max_tokens, pause_turn, "
                "and refusal stop reasons and how to branch on each."
            ),
        },
        {
            "title": "Building Reliable Tool-Use Loops",
            "url": "https://eng-blog.example.com/tool-loops",
            "snippet": (
                "Covers common pitfalls: treating max_tokens as done, "
                "missing max_turns ceilings, and pause_turn mishandling."
            ),
        },
    ],
    "hub and spoke multi agent pattern": [
        {
            "title": "Coordinator-Subagent Architectures",
            "url": "https://docs.example.com/hub-spoke",
            "snippet": (
                "A lead/orchestrator agent routes subtasks to specialist "
                "subagents and aggregates their outputs."
            ),
        },
        {
            "title": "When to use hub-and-spoke vs. flat multi-agent",
            "url": "https://eng-blog.example.com/multi-agent-tradeoffs",
            "snippet": (
                "Hub-and-spoke centralizes routing decisions and keeps "
                "subagents stateless and composable."
            ),
        },
    ],
}

# Fake page bodies keyed by URL, returned by fetch_page.
_MOCK_PAGE_BODIES = {
    "https://docs.example.com/stop-reason": (
        "stop_reason can be tool_use, end_turn, max_tokens, stop_sequence, "
        "pause_turn, or refusal. Only end_turn and stop_sequence represent "
        "a clean, intentional halt. max_tokens means the response was cut "
        "off and must not be treated as a finished answer. pause_turn "
        "appears with long-running server tools and should be resumed by "
        "re-sending the conversation, not by executing a local tool."
    ),
    "https://eng-blog.example.com/tool-loops": (
        "The most common production bug in agent loops is conflating "
        "'no more tool calls this turn' with 'task complete'. A second "
        "common bug is omitting a max_turns safety ceiling, which lets a "
        "stuck retry loop run unbounded."
    ),
    "https://docs.example.com/hub-spoke": (
        "In a hub-and-spoke design, the orchestrator owns task "
        "decomposition and sequencing. Subagents receive an explicit, "
        "minimal context packet for their step only -- they do not see the "
        "full orchestrator transcript -- which keeps them composable and "
        "easier to test in isolation."
    ),
    "https://eng-blog.example.com/multi-agent-tradeoffs": (
        "Hub-and-spoke trades some latency (everything passes through the "
        "hub) for much simpler reasoning about ordering, error handling, "
        "and auditability versus a flat mesh of agents calling each other "
        "directly."
    ),
}


def tool_web_search(tool_input: dict) -> str:
    query = tool_input["query"].strip().lower()
    # naive substring match against our mock index
    for key, results in _MOCK_SEARCH_INDEX.items():
        if key in query or query in key:
            return json.dumps(results, indent=2)
    return json.dumps(
        {"results": [], "note": "No matches in mock index for this query."}
    )


def tool_fetch_page(tool_input: dict) -> str:
    url = tool_input["url"]
    body = _MOCK_PAGE_BODIES.get(url)
    if body is None:
        return f"Error: no mock content registered for URL {url!r}"
    return body


_RESEARCH_NOTEBOOK: list[dict] = []  # populated as save_finding is called


def tool_save_finding(tool_input: dict) -> str:
    entry = {"fact": tool_input["fact"], "source_url": tool_input["source_url"]}
    _RESEARCH_NOTEBOOK.append(entry)
    return f"Saved finding #{len(_RESEARCH_NOTEBOOK)}: {entry['fact'][:80]}..."


def get_research_notebook() -> list[dict]:
    """Read-only accessor so the orchestrator/report can inspect findings."""
    return list(_RESEARCH_NOTEBOOK)


def reset_research_notebook() -> None:
    _RESEARCH_NOTEBOOK.clear()


# ==========================================================================
# DOCUMENT PIPELINE TOOLS (extraction -> analysis -> validation)
# ==========================================================================

PIPELINE_TOOLS = [
    {
        "name": "extract_document",
        "description": (
            "Extract structured fields (title, date, parties, key clauses) "
            "from a raw document string. This MUST be the first step of "
            "the pipeline; its output is required input for analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_text": {"type": "string"},
            },
            "required": ["raw_text"],
        },
    },
    {
        "name": "analyze_content",
        "description": (
            "Analyze previously-extracted structured fields and produce "
            "risk flags / summary insights. Requires extraction to have "
            "already completed; do not call with raw, unextracted text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "extracted_fields": {
                    "type": "object",
                    "description": "The structured object returned by extract_document",
                },
            },
            "required": ["extracted_fields"],
        },
    },
    {
        "name": "validate_output",
        "description": (
            "Validate that an analysis result meets quality/completeness "
            "requirements before it is released. Must be called last."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_result": {"type": "object"},
            },
            "required": ["analysis_result"],
        },
    },
]


def tool_extract_document(tool_input: dict) -> str:
    raw = tool_input["raw_text"]
    # Toy deterministic "extraction" -- in production this would be a real
    # parser or an LLM-based extraction subagent (which is exactly what
    # subagents.py's ExtractorAgent wraps this in).
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    title = lines[0] if lines else "UNKNOWN"
    parties = [l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("parties:")]
    date = next((l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("date:")), "UNKNOWN")
    clauses = [l for l in lines if l.lower().startswith("clause")]

    extracted = {
        "title": title,
        "date": date,
        "parties": parties[0].split(",") if parties else [],
        "clauses": clauses,
        "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return json.dumps(extracted, indent=2)


def tool_analyze_content(tool_input: dict) -> str:
    fields = tool_input["extracted_fields"]
    clauses = fields.get("clauses", [])
    risk_flags = []
    for c in clauses:
        low = c.lower()
        if "terminat" in low:  # matches "terminate" and "termination"
            risk_flags.append({"clause": c, "risk": "termination terms present, review notice period"})
        if "liability" in low:
            risk_flags.append({"clause": c, "risk": "liability clause present, check cap amount"})
        if "auto-renew" in low or "automatic renewal" in low:
            risk_flags.append({"clause": c, "risk": "auto-renewal clause, confirm opt-out window"})

    analysis = {
        "title": fields.get("title"),
        "parties": fields.get("parties"),
        "clause_count": len(clauses),
        "risk_flags": risk_flags,
        "summary": (
            f"Document '{fields.get('title')}' between "
            f"{', '.join(fields.get('parties', [])) or 'unknown parties'} "
            f"contains {len(clauses)} clause(s) and {len(risk_flags)} flagged risk(s)."
        ),
    }
    return json.dumps(analysis, indent=2)


def tool_validate_output(tool_input: dict) -> str:
    result = tool_input["analysis_result"]
    errors = []
    if not result.get("title") or result.get("title") == "UNKNOWN":
        errors.append("Missing or unknown document title.")
    if not result.get("parties"):
        errors.append("No parties identified.")
    if "risk_flags" not in result:
        errors.append("Analysis result missing risk_flags field.")

    validation = {
        "valid": len(errors) == 0,
        "errors": errors,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return json.dumps(validation, indent=2)


# ==========================================================================
# REGISTRIES — map tool name -> python function. Used by agent_loop's
# tool_executor callback. Each subagent gets only the slice it needs.
# ==========================================================================

RESEARCH_TOOL_REGISTRY = {
    "web_search": tool_web_search,
    "fetch_page": tool_fetch_page,
    "save_finding": tool_save_finding,
}

PIPELINE_TOOL_REGISTRY = {
    "extract_document": tool_extract_document,
    "analyze_content": tool_analyze_content,
    "validate_output": tool_validate_output,
}


def make_executor(registry: dict):
    """Build a tool_executor(name, input) -> str closure over a registry."""

    def _executor(name: str, tool_input: dict) -> str:
        fn = registry.get(name)
        if fn is None:
            return f"Error: unknown tool '{name}'"
        return fn(tool_input)

    return _executor
