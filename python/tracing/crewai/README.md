# CrewAI Respan Tracing Examples

This directory contains CrewAI examples wired to the local
`respan-instrumentation-crewai` package. The examples are organized by CrewAI
capability so users can run one focused script and inspect the exported spans.

## Setup

```bash
cd python/tracing/crewai
poetry install
```

Set `RESPAN_API_KEY` in `.env` or in your shell. The scripts route LLM calls
through the Respan gateway, so no separate OpenAI key is required. Optional
settings:

- `RESPAN_BASE_URL` defaults to `https://api.respan.ai/api`
- `RESPAN_MODEL` defaults to `gpt-4o-mini`
- `RESPAN_CREWAI_RUN_ID` overrides the run id in params examples

Run any example:

```bash
poetry run python 01_hello_world.py
```

The examples load `.env` from this directory, the repository root, or the
adjacent `respan` checkout. They also default `XDG_DATA_HOME` to
`/tmp/respan-crewai-data` so CrewAI local storage does not write into an
unwritable IDE home directory.

## Examples

| Example | CrewAI ability shown |
|---------|----------------------|
| `01_hello_world.py` | Single `Agent`, `Task`, `Crew`, and `kickoff()` |
| `02_tool_use.py` | `@tool` registration and tool-call tracing |
| `03_multi_agent_sequential.py` | Multiple agents, `Process.sequential`, and task `context` |
| `04_structured_output.py` | `output_pydantic` structured task output |
| `05_respan_params.py` | Respan custom params, customer fields, thread, metadata, and evaluation identifiers |
| `06_kickoff_variants.py` | `kickoff`, `kickoff_async`, `akickoff`, `kickoff_for_each`, and `kickoff_for_each_async` |
| `07_hierarchical_planning_streaming.py` | `Process.hierarchical`, manager LLM, crew planning, and streaming output |
| `08_task_controls_callbacks_guardrails.py` | Task `async_execution`, `markdown`, `output_file`, task callbacks, step callbacks, and guardrails |
| `09_conditional_task.py` | `ConditionalTask` branching based on previous task output |
| `10_knowledge_and_memory.py` | `StringKnowledgeSource`, agent/crew knowledge sources, and memory |
| `11_flow_routing.py` | `Flow`, `@start`, `@listen`, `@router`, and `and_` conditions |
| `12_project_decorators.py` | `CrewBase`, `@agent`, `@task`, `@crew`, `@before_kickoff`, and `@after_kickoff` |
| `13_lite_agent.py` | Direct `LiteAgent.kickoff()` and `LiteAgent.kickoff_async()` |
| `14_output_json_response_model.py` | `output_json` and `response_model` structured output variants |
| `15_global_hooks.py` | Global LLM and tool hooks with `before_*` and `after_*` decorators |
| `complex_edge_cases.py` | Advanced combined case with nested tools, custom params, long payloads, and cleanup checks |

## Coverage Notes

The runnable examples cover the core public APIs exposed by CrewAI 1.14.x:
top-level agents, tasks, crews, processes, LLM-based execution, tools,
structured outputs, kickoff variants, hierarchical orchestration, planning,
streaming, conditional tasks, knowledge, memory, flows, project decorators,
LiteAgent, callbacks, guardrails, and hooks.

Some CrewAI APIs are intentionally not included as default runnable scripts:

- `Crew.train`, `Crew.test`, and `Crew.replay` are stateful evaluation and
  replay workflows that depend on prior runs, generated task IDs, and local
  training files.
- `human_input` and flow human feedback pause for interactive console input.
- `a2a`, `mcps`, app integrations, file attachments, skills, and CLI commands
  require external servers, service credentials, generated projects, or
  optional packages beyond the base tracing example.

Those are still useful integration targets, but they are not good base unit
examples for a folder meant to run reliably with only a Respan key.
