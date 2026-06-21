# Lab 1.1 — Building the Agentic Loop: Orchestration & Subagent Coordination

A small, runnable project implementing three required patterns:

1. **A stable agentic loop that reads `stop_reason` correctly**
2. **Coordinator–subagent (hub-and-spoke) delegation**
3. **Explicit context passing + programmatically enforced step order**

```
lab1_1/
├── agent_loop.py     # core stop_reason state machine (used by every agent)
├── tools.py          # tool schemas + deterministic mock executors
├── subagents.py       # specialist subagents (research, extract, analyze, validate, summarize, translate)
├── orchestrator.py    # the hub: TaskRouter, DocumentPipeline, ResearchOrchestrator
├── main.py            # runs all 3 demos against the real Anthropic API
├── test_agent_loop_offline.py  # offline unit tests, no API key/network needed
├── requirements.txt    # third-party deps (anthropic, python-dotenv)
├── .env.example        # template for your API key (safe to commit)
├── .env                # your real key goes here (gitignored)
├── .gitignore
└── README.md
```

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env        # then edit .env and paste in your real key
python3 main.py
```

```bash
OR
cd /Users/ajaysingh/projects/rnd/Lab-1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python test_agent_loop_offline.py 
```

`main.py` calls `load_dotenv()` on startup, so `.env` is picked up
automatically — no need to `export` the key manually. You can still use
`export ANTHROPIC_API_KEY=sk-ant-...` instead if you prefer; either way works.
`.env` is listed in `.gitignore` so your real key is never committed —
only the placeholder `.env.example` is meant to be checked in.

To sanity-check the loop logic without burning API calls:

```bash
python3 test_agent_loop_offline.py
```

---

## 1. Reading `stop_reason` correctly

This is the part most implementations get subtly wrong. `agent_loop.run_agent_loop`
treats `stop_reason` as a state machine with **six** branches, not two:

| `stop_reason`     | Correct action                                             | Common bug it prevents |
|--------------------|--------------------------------------------------------------|--------------------------|
| `tool_use`         | Execute requested tool(s), append `tool_result`, loop again | — |
| `end_turn`         | Halt. This is the real "done."                              | — |
| `stop_sequence`    | Halt (custom stop sequence fired)                            | — |
| `max_tokens`       | Halt, but flag as **truncated**, not a finished answer       | Treating cut-off output as a valid final answer |
| `pause_turn`       | Resend the conversation unchanged; do **not** run a local tool | Misinterpreting server-side long-running tool pauses as a tool_use request |
| `refusal`          | Halt immediately; do not retry the same request in a loop    | Hammering a declined request |
| *(anything else)*  | Raise loudly                                                  | Silently mis-handling a future/unknown stop_reason |

A `LoopResult` dataclass reports `halted_cleanly` and `truncated` as separate
booleans so callers can never confuse "no more tool calls this turn" with
"task complete." There's also a hard `max_turns` ceiling — without one, a
model stuck retrying a failing tool runs forever.

Run `test_agent_loop_offline.py` to see this exercised directly with a
scripted mock client: it proves the loop does NOT execute tools on
`pause_turn`, does NOT treat `max_tokens` as success, and raises on an
unrecognized `stop_reason` rather than guessing.

## 2. Hub-and-spoke coordination

`orchestrator.py` contains three orchestrators, each delegating to subagents
in `subagents.py`:

- **`TaskRouter`** — classifies an incoming task (`summarize` / `translate` /
  `validate`) with a small constrained LLM call, then dispatches via a plain
  dict lookup to `SummarizerAgent`, `TranslatorAgent`, or `ValidatorTextAgent`.
- **`DocumentPipeline`** — runs `ExtractorAgent` → `AnalyzerAgent` →
  `ValidatorAgent` in enforced order (see §3).
- **`ResearchOrchestrator`** — decomposes a topic into sub-questions and
  delegates each to a fresh `ResearchSubagent`, which runs its own
  `tool_use`/`tool_result` loop (`web_search` → `fetch_page` → `save_finding`)
  until it reaches `end_turn`, then synthesizes a final report from all
  sub-answers.

Subagents never call each other. All sequencing, routing, and error handling
lives in the orchestrator. Subagents are stateless, narrow-purpose, and only
see what's explicitly handed to them — which is the next requirement.

## 3. Explicit context + programmatic order enforcement

`DocumentPipeline.run()` enforces extraction → analysis → validation **in
Python control flow**, not just in a prompt:

```python
extracted = self._extract(raw_document_text)          # Stage 1
if not extracted.success:
    return PipelineRunResult(completed=False, failed_at="extraction")

analyzed = self._analyze(extracted)                     # Stage 2 — requires Stage 1's result object
if not analyzed.success:
    return PipelineRunResult(completed=False, failed_at="analysis")

validated = self._validate(analyzed)                    # Stage 3 — requires Stage 2's result object
```

Two layers of enforcement:

1. **Structural**: `_analyze(extracted)` takes Stage 1's `SubagentResult` as
   a required argument and raises `PipelineOrderError` if it's ever called
   with a failed result — even if someone bypasses `run()` and calls it
   directly (see `test_pipeline_order_enforcement` in the offline tests).
2. **Tool-scoping**: each pipeline subagent is given access to exactly one
   tool (`ExtractorAgent` can only call `extract_document`, etc.), so even
   the model itself has no path to skip a stage.

Each stage also passes an **explicit, minimal context packet** — not the
full orchestrator transcript:

- `AnalyzerAgent` receives only `extracted_fields` (the structured output of
  extraction), never the raw document text.
- `ValidatorAgent` receives only `analysis_result`, never the raw text or
  the original extracted fields.

This keeps subagents composable and testable in isolation, and keeps the
orchestrator the single place where you can audit *why* a particular
sequence happened.

## What `main.py` demonstrates

- **Demo 1**: Research orchestrator decomposing a topic, running two
  parallel-in-spirit (sequential-in-code) `ResearchSubagent` delegations,
  each exercising a real multi-turn `tool_use` loop, then synthesizing a report.
- **Demo 2**: Three different task types routed to three different
  specialists by `TaskRouter`.
- **Demo 3a**: `DocumentPipeline` happy path — all three stages succeed.
- **Demo 3b**: `DocumentPipeline` fed a deliberately empty/garbage document
  — validation correctly fails and the run report shows exactly which stage
  halted execution, proving downstream stages don't silently run on bad data.

## Adapting this for production

- Swap the mock tool executors in `tools.py` (`tool_web_search`,
  `tool_fetch_page`) for real implementations (a search API, `requests`, etc.).
- `ExtractorAgent`/`AnalyzerAgent`/`ValidatorAgent`'s underlying tools
  (`tool_extract_document`, etc.) are toy deterministic parsers — replace
  with real NLP/parsing logic or another LLM call as needed.
- For true parallel subagent execution (vs. this lab's sequential calls for
  readability), wrap `ResearchSubagent.run()` calls in a thread pool or
  `asyncio.gather` — the subagent contract (explicit input → typed
  `SubagentResult`) is already parallel-safe since subagents share no state
  (each call resets its own notebook/context).
