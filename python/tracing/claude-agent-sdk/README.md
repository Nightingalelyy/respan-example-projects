# Claude Agent SDK + Local Respan Instrumentation

This directory contains two Claude Agent SDK tracing examples that use local
Respan packages from the sibling `respan` checkout instead of published builds.

## Setup

The examples now rely on package-manager-installed local dependencies from
`pyproject.toml`; they do not modify `sys.path` at runtime.

Recommended:

```bash
cd python/tracing/claude-agent-sdk
poetry install
```

The `pyproject.toml` includes Poetry path dependencies for the sibling local
`respan` checkout, including the local
`respan-instrumentation-claude-agent-sdk` and local `respan-tracing` packages.
After `poetry install`, run the examples with `poetry run python ...`.

Manual `uv` setup:

```bash
cd python/tracing/claude-agent-sdk
uv venv .venv
uv pip install --python .venv/bin/python python-dotenv
uv pip install --python .venv/bin/python \
  -e /home/yuyang/KeywordsAI/respan/python-sdks/respan-sdk \
  -e /home/yuyang/KeywordsAI/respan/python-sdks/respan-tracing \
  -e /home/yuyang/KeywordsAI/respan/python-sdks/respan \
  -e /home/yuyang/KeywordsAI/respan/python-sdks/instrumentations/respan-instrumentation-claude-agent-sdk
```

The scripts load environment variables from the example repo root `.env` at
`/home/yuyang/KeywordsAI/respan-example-projects/.env`.

If your local `respan` checkout is not the sibling repo at
`../../../../respan`, update the four Poetry path dependencies in
`pyproject.toml` to point at your local `respan`, `respan-sdk`,
`respan-tracing`, and `respan-instrumentation-claude-agent-sdk` package paths.

## Basic Example

The fastest way to see a simple Claude Agent SDK trace on Respan platform is:

```bash
poetry run python basic_platform_example.py
```

What it does:

- sends one basic `claude_agent_sdk.query()` request
- traces it with `respan-instrumentation-claude-agent-sdk`
- prints the Claude result locally
- prints the exact platform filters to find the trace

Look up the trace on platform with:

- `customer_identifier = claude-agent-sdk-basic-example`
- `metadata.example_name = claude_agent_sdk_basic_platform_example`

## Advanced Example

The complex edge-case example is still available:

```bash
poetry run python complex_edge_cases_test.py
```

## What The Advanced Example Covers

- Basic `query()` tracing
- Single-tool query with Claude MCP tools
- Multi-tool query with chained tool usage
- Tool error handling
- Stateful `ClaudeSDKClient` multi-turn session

Look up the advanced trace on platform with:

- `customer_identifier = claude-agent-sdk-complex-edge-cases-v2`
- `metadata.example_name = claude_agent_sdk_complex_edge_cases`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESPAN_GATEWAY_API_KEY` or `RESPAN_API_KEY` | Yes | Used for both Respan tracing and Anthropic-compatible gateway auth |
| `RESPAN_BASE_URL` | No | Defaults to `https://api.respan.ai/api` |
| `CLAUDE_AGENT_MODEL` | No | Defaults to `sonnet` |
