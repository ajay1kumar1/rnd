"""
orchestrator.py

The hub in the hub-and-spoke pattern. Two orchestrator classes:

  1. TaskRouter        -- routes free-form tasks ("summarize", "translate",
                           "validate") to the matching subagent. Routing
                           decision can be made by the orchestrator's own
                           LLM call (classify-then-dispatch) OR by simple
                           keyword rules; both are shown.

  2. DocumentPipeline   -- runs extraction -> analysis -> validation in a
                           PROGRAMMATICALLY ENFORCED order. This is the
                           "pass explicit context + enforce step order"
                           requirement. Order is not a suggestion in a
                           prompt -- it is Python control flow. Stage 2
                           literally cannot run before stage 1 produces a
                           successful result object, because stage 2's
                           function signature requires stage 1's output as
                           an argument.

Design principle: subagents never talk to each other. All coordination,
sequencing, and error handling lives in the orchestrator. Subagents are
stateless and only see what the orchestrator explicitly hands them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic

from subagents import (
    SubagentResult,
    SummarizerAgent,
    TranslatorAgent,
    ValidatorTextAgent,
    ExtractorAgent,
    AnalyzerAgent,
    ValidatorAgent,
    ResearchSubagent,
)


MODEL = "claude-sonnet-4-6"


# ==========================================================================
# 1. TASK ROUTER -- hub-and-spoke dispatch to summarize/translate/validate
# ==========================================================================

class PipelineOrderError(Exception):
    """Raised when code attempts to run a pipeline stage out of order."""


class TaskRouter:
    """
    Lead/orchestrator agent that classifies an incoming task and routes it
    to exactly one specialist subagent. The routing decision itself is made
    with a small, constrained LLM call (a classifier), and dispatch is then
    a plain Python dict lookup -- so even if the classifier is uncertain,
    the set of possible outcomes is fixed and auditable.
    """

    VALID_ROUTES = {"summarize", "translate", "validate"}

    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self.summarizer = SummarizerAgent(client)
        self.translator = TranslatorAgent(client)
        self.validator = ValidatorTextAgent(client)

    def classify(self, task_description: str) -> str:
        """Ask the model to pick exactly one route. Returns one of
        VALID_ROUTES. Falls back to keyword heuristics if the model
        response is somehow not a clean match (defensive, not happy-path)."""
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=20,
            system=(
                "Classify the user's task into exactly one of: summarize, "
                "translate, validate. Reply with ONLY that single word, "
                "nothing else."
            ),
            messages=[{"role": "user", "content": task_description}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip().lower()
        for route in self.VALID_ROUTES:
            if route in text:
                return route

        # Defensive fallback -- keyword heuristic
        low = task_description.lower()
        if "translat" in low:
            return "translate"
        if "valid" in low or "check" in low:
            return "validate"
        return "summarize"

    def route_and_run(self, *, task_description: str, payload: dict) -> SubagentResult:
        """
        payload contents depend on route:
          summarize -> {"text": ...}
          translate -> {"text": ..., "target_language": ...}
          validate  -> {"text": ..., "requirements": [...]}
        """
        route = self.classify(task_description)
        print(f"  [TaskRouter] classified task as: '{route}'")

        if route == "summarize":
            return self.summarizer.run(text=payload["text"])
        elif route == "translate":
            return self.translator.run(
                text=payload["text"], target_language=payload["target_language"]
            )
        elif route == "validate":
            return self.validator.run(
                text=payload["text"], requirements=payload["requirements"]
            )
        else:
            raise RuntimeError(f"Unreachable: unknown route {route!r}")


# ==========================================================================
# 2. DOCUMENT PIPELINE -- programmatically ordered extraction -> analysis
#    -> validation. Explicit context is passed at each handoff.
# ==========================================================================

@dataclass
class PipelineStageRecord:
    stage: str
    success: bool
    output: Any
    error: Optional[str]


@dataclass
class PipelineRunResult:
    completed: bool
    stages: list[PipelineStageRecord] = field(default_factory=list)
    final_output: Optional[dict] = None
    failed_at: Optional[str] = None


class DocumentPipeline:
    """
    Orchestrates: extract_document -> analyze_content -> validate_output

    ORDER ENFORCEMENT IS PROGRAMMATIC, NOT PROMPT-BASED:
      - run() calls self._extract() first. Its return value (a
        SubagentResult) is the ONLY way analysis gets its input.
      - self._analyze() takes `extracted: SubagentResult` as a required
        positional argument. There is no code path that constructs an
        AnalyzerAgent call without a prior successful ExtractorAgent
        result -- you would have to delete the type-checked gate below
        to skip the order.
      - If any stage fails (success=False), the pipeline halts immediately
        and reports which stage failed, instead of feeding bad/partial
        data forward into the next specialist.

    This mirrors the lab's required example: "a document pipeline where
    extraction must finish before analysis begins."
    """

    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self.extractor = ExtractorAgent(client)
        self.analyzer = AnalyzerAgent(client)
        self.validator = ValidatorAgent(client)

    def run(self, *, raw_document_text: str) -> PipelineRunResult:
        stages: list[PipelineStageRecord] = []

        # ---- Stage 1: EXTRACTION (must run first; nothing depends on
        # anything else here, so it is always safe as the entry point) ----
        print("  [DocumentPipeline] Stage 1/3: extraction")
        extracted = self._extract(raw_document_text)
        stages.append(PipelineStageRecord(
            stage="extraction", success=extracted.success,
            output=extracted.output, error=extracted.error,
        ))
        if not extracted.success:
            print(f"  [DocumentPipeline] HALTED after extraction: {extracted.error}")
            return PipelineRunResult(completed=False, stages=stages, failed_at="extraction")

        # ---- Stage 2: ANALYSIS (programmatically gated on Stage 1) ----
        print("  [DocumentPipeline] Stage 2/3: analysis")
        analyzed = self._analyze(extracted)  # <-- requires Stage 1's result object
        stages.append(PipelineStageRecord(
            stage="analysis", success=analyzed.success,
            output=analyzed.output, error=analyzed.error,
        ))
        if not analyzed.success:
            print(f"  [DocumentPipeline] HALTED after analysis: {analyzed.error}")
            return PipelineRunResult(completed=False, stages=stages, failed_at="analysis")

        # ---- Stage 3: VALIDATION (programmatically gated on Stage 2) ----
        print("  [DocumentPipeline] Stage 3/3: validation")
        validated = self._validate(analyzed)  # <-- requires Stage 2's result object
        stages.append(PipelineStageRecord(
            stage="validation", success=validated.success,
            output=validated.output, error=validated.error,
        ))
        if not validated.success:
            print(f"  [DocumentPipeline] HALTED after validation: {validated.error}")
            return PipelineRunResult(completed=False, stages=stages, failed_at="validation")

        print("  [DocumentPipeline] All 3 stages completed successfully.")
        return PipelineRunResult(
            completed=True,
            stages=stages,
            final_output={
                "extracted": extracted.output,
                "analysis": analyzed.output,
                "validation": validated.output,
            },
        )

    # ---- Private stage methods: each builds an EXPLICIT, MINIMAL context
    # packet for its subagent rather than forwarding the whole pipeline
    # history. The analyzer never sees raw_document_text; the validator
    # never sees raw_document_text or the original extracted fields. ----

    def _extract(self, raw_document_text: str) -> SubagentResult:
        return self.extractor.run(raw_text=raw_document_text)

    def _analyze(self, extracted: SubagentResult) -> SubagentResult:
        if not extracted.success:
            # Defense in depth: even if a caller bypasses run() and calls
            # _analyze directly, refuse to proceed on a failed extraction.
            raise PipelineOrderError(
                "_analyze() called with a failed extraction result. "
                "Analysis cannot run before extraction succeeds."
            )
        # Explicit context packet: ONLY the structured fields, nothing else.
        return self.analyzer.run(extracted_fields=extracted.output)

    def _validate(self, analyzed: SubagentResult) -> SubagentResult:
        if not analyzed.success:
            raise PipelineOrderError(
                "_validate() called with a failed analysis result. "
                "Validation cannot run before analysis succeeds."
            )
        # Explicit context packet: ONLY the analysis result.
        return self.validator.run(analysis_result=analyzed.output)


# ==========================================================================
# 3. RESEARCH ASSISTANT ORCHESTRATOR -- demonstrates the loop-until-done
#    pattern (the lab's first requirement) at the orchestrator level: it
#    keeps delegating sub-questions to ResearchSubagent until it judges the
#    overall research task complete, then synthesizes a final report.
# ==========================================================================

@dataclass
class ResearchRunResult:
    sub_answers: list[dict]
    final_report: str


class ResearchOrchestrator:
    """
    Decomposes a broad research task into sub-questions, delegates each to
    a fresh ResearchSubagent (hub-and-spoke), and synthesizes a final
    report once all sub-questions are answered. The orchestrator's own
    "keep going until done" loop is a simple, explicit, programmatic
    iteration over a fixed question list -- deliberately NOT another nested
    tool-use loop, to keep the two required patterns (stop_reason loop,
    and hub-and-spoke) visibly distinct in this lab rather than blurred
    together.
    """

    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self.research_agent = ResearchSubagent(client)

    def decompose(self, topic: str, n_questions: int = 2) -> list[str]:
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=(
                f"Break the given research topic into exactly {n_questions} "
                "specific, independently-answerable sub-questions. Reply "
                "with ONLY the questions, one per line, no numbering."
            ),
            messages=[{"role": "user", "content": topic}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        questions = [q.strip("-• ").strip() for q in text.splitlines() if q.strip()]
        return questions[:n_questions]

    def run(self, *, topic: str, n_questions: int = 2) -> ResearchRunResult:
        questions = self.decompose(topic, n_questions=n_questions)
        print(f"  [ResearchOrchestrator] decomposed into {len(questions)} sub-question(s):")
        for q in questions:
            print(f"    - {q}")

        sub_answers = []
        for i, q in enumerate(questions, 1):
            print(f"  [ResearchOrchestrator] delegating sub-question {i}/{len(questions)}")
            result = self.research_agent.run(question=q)
            sub_answers.append({
                "question": q,
                "success": result.success,
                "answer": result.output["answer"] if result.success else None,
                "findings": result.output["findings"] if result.success else [],
                "error": result.error,
            })

        # Synthesis: orchestrator combines subagent outputs into one report.
        synthesis_input = "\n\n".join(
            f"Q: {a['question']}\nA: {a['answer'] or '[no answer -- ' + str(a['error']) + ']'}"
            for a in sub_answers
        )
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=(
                "You are a research report writer. Combine the following "
                "Q&A pairs from specialist researchers into one coherent "
                "report (a short intro, then the synthesized findings). "
                "Do not introduce facts that are not present in the Q&A."
            ),
            messages=[{"role": "user", "content": f"Topic: {topic}\n\n{synthesis_input}"}],
        )
        final_report = "".join(b.text for b in resp.content if b.type == "text").strip()

        return ResearchRunResult(sub_answers=sub_answers, final_report=final_report)
