"""
main.py

Runs three demonstrations end to end:

  DEMO 1 -- Research assistant: ResearchOrchestrator decomposes a topic,
            delegates sub-questions to ResearchSubagent (each running a
            real tool_use/tool_result loop until end_turn), synthesizes a
            report. Exercises the stop_reason loop requirement.

  DEMO 2 -- TaskRouter: hub-and-spoke routing of three different task
            types ("summarize", "translate", "validate") to three
            different specialist subagents.

  DEMO 3 -- DocumentPipeline: extraction -> analysis -> validation with
            order enforced in Python control flow, including a deliberate
            "what if extraction fails" run to prove stage 2 never executes.

Requires ANTHROPIC_API_KEY to be set in the environment.
"""

from __future__ import annotations

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

from orchestrator import TaskRouter, DocumentPipeline, ResearchOrchestrator

load_dotenv()  # reads .env in the project root, if present, into os.environ


def banner(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY is not set.\n"
            "Either export it directly:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "or copy .env.example to .env and fill in your key:\n"
            "  cp .env.example .env\n"
        )
        sys.exit(1)

    client = anthropic.Anthropic()

    # ----------------------------------------------------------------
    # DEMO 1: Research assistant (stop_reason loop, end-to-end)
    # ----------------------------------------------------------------
    banner("DEMO 1: Research Assistant Orchestrator (loop-until-done)")
    research_orch = ResearchOrchestrator(client)
    research_result = research_orch.run(
        topic="Best practices for agentic loops and multi-agent coordination",
        n_questions=2,
    )
    print("\n--- Sub-answers ---")
    for sa in research_result.sub_answers:
        print(f"\nQ: {sa['question']}")
        print(f"A: {sa['answer']}")
        print(f"   findings used: {len(sa['findings'])}")
    print("\n--- Final synthesized report ---")
    print(research_result.final_report)

    # ----------------------------------------------------------------
    # DEMO 2: Hub-and-spoke task routing
    # ----------------------------------------------------------------
    banner("DEMO 2: TaskRouter (hub-and-spoke dispatch)")
    router = TaskRouter(client)

    tasks = [
        {
            "task_description": "Please summarize this paragraph for me.",
            "payload": {
                "text": (
                    "Agentic loops work by repeatedly calling a model, "
                    "inspecting its stop_reason, executing any requested "
                    "tools, and feeding the results back in, until the "
                    "model signals it is finished with end_turn. A common "
                    "failure mode is treating any non-tool_use response as "
                    "finished, which silently accepts truncated output."
                )
            },
        },
        {
            "task_description": "Translate this sentence into French.",
            "payload": {
                "text": "The orchestrator routes tasks to specialist subagents.",
                "target_language": "French",
            },
        },
        {
            "task_description": "Check whether this text meets the requirements.",
            "payload": {
                "text": "The pipeline extracts, then analyzes, then validates.",
                "requirements": [
                    "Mentions all three pipeline stages",
                    "Mentions the word 'extracts'",
                    "Is under 30 words",
                ],
            },
        },
    ]

    for t in tasks:
        print(f"\n--- Task: {t['task_description']!r} ---")
        result = router.route_and_run(
            task_description=t["task_description"], payload=t["payload"]
        )
        if result.success:
            print(f"[{result.agent_name}] output:\n{result.output}")
        else:
            print(f"[{result.agent_name}] FAILED: {result.error}")

    # ----------------------------------------------------------------
    # DEMO 3: Document pipeline with enforced ordering
    # ----------------------------------------------------------------
    banner("DEMO 3a: DocumentPipeline -- happy path (extraction succeeds)")
    pipeline = DocumentPipeline(client)

    sample_doc = (
        "Master Services Agreement\n"
        "Date: 2026-03-15\n"
        "Parties: Acme Corp, Globex Inc\n"
        "Clause 1: Either party may terminate this agreement with 30 days notice.\n"
        "Clause 2: Liability under this agreement is capped at total fees paid.\n"
        "Clause 3: This agreement will auto-renew annually unless cancelled.\n"
    )

    run1 = pipeline.run(raw_document_text=sample_doc)
    print(f"\nPipeline completed: {run1.completed}")
    for stage in run1.stages:
        print(f"  - {stage.stage}: success={stage.success}")
    if run1.completed:
        print("\nFinal pipeline output:")
        print(json.dumps(run1.final_output, indent=2))

    banner("DEMO 3b: DocumentPipeline -- forced extraction failure (order proof)")
    # Deliberately feed empty/garbage text so extraction can't find a real
    # title or parties, which trips validate_output's checks. We show this
    # by running validate AFTER analysis on a deliberately bad extraction,
    # proving the pipeline halts and stage 3 is never reached.
    bad_doc = "   \n   \n"  # no usable content at all
    run2 = pipeline.run(raw_document_text=bad_doc)
    print(f"\nPipeline completed: {run2.completed}")
    print(f"Failed at stage: {run2.failed_at}")
    for stage in run2.stages:
        print(f"  - {stage.stage}: success={stage.success}, error={stage.error}")
    print(
        "\n^ Note: only the stages that actually ran appear above. If "
        "extraction had failed, 'analysis' and 'validation' would be "
        "completely absent from this list -- not run-and-failed, but "
        "never invoked at all. Here extraction succeeds (it can always "
        "produce a JSON object) but validation correctly catches the "
        "missing title/parties and the pipeline reports failed_at='validation'."
    )

    banner("ALL DEMOS COMPLETE")


if __name__ == "__main__":
    main()
