# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**newsletterdemo** — WAT (Workflow Automation Tools) demo project.

> Update this section with a one-line description, the tech stack, and the
> entry point once the project takes shape.

## WAT Tools & Workflows

This project is organized around composable **WAT tools** (single-purpose
units of work) wired together into **workflows** (ordered sequences of tools).

### Conventions

- **Tools** live in `tools/` — one tool per file, each exposing a single
  callable entry point with typed inputs and outputs.
- **Workflows** live in `workflows/` — each composes tools in a defined order
  and owns its own error handling and logging.
- Keep tools pure and side-effect-aware: a tool should declare what it reads
  and writes. Workflows orchestrate; tools execute.
- Configuration comes from environment variables (see `.env`), never hardcoded.

### Adding a new tool

1. Create `tools/<tool_name>.py` (or matching the project's language).
2. Define a single entry point; validate inputs at the boundary.
3. Read any config from the environment, not from literals.
4. Register the tool in the workflow that uses it.

### Adding a new workflow

1. Create `workflows/<workflow_name>.py`.
2. Import and sequence the required tools.
3. Handle failures explicitly — fail fast and log context.

## Setup

```bash
cp .env.example .env   # if an example file exists
# fill in the required secrets in .env
```

## Commands

> Fill these in as the project grows.

```bash
# install deps
# run a workflow
# run tests
# lint / format
```

## Working agreements for Claude

- Read `.env` keys for required configuration; never commit real secrets.
- Match the style and structure of existing tools/workflows when adding code.
- Prefer small, composable tools over large monolithic functions.
- Run the relevant tests/lint before declaring a change complete.
