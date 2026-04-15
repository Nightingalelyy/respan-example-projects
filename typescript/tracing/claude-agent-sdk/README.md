# Claude Agent SDK + Local Respan Instrumentation (TypeScript)

This directory contains TypeScript Claude Agent SDK tracing examples that use
local Respan packages from the sibling `respan` checkout instead of published
builds.

## Setup

Recommended:

```bash
cd typescript/tracing/claude-agent-sdk
yarn install
```

The `package.json` uses local file dependencies that point at the sibling local
`respan` checkout, including:

- `@respan/respan`
- `@respan/respan-sdk`
- `@respan/tracing`
- `@respan/instrumentation-claude-agent-sdk`

The scripts load environment variables from the example repo root `.env` at:

`/home/yuyang/KeywordsAI/respan-example-projects/.env`

If your local `respan` checkout is not the sibling repo at `../../../../respan`,
update the four local `file:` dependency paths in `package.json`.

If one of the local Respan packages has not been built yet and `dist/` is
missing, build it from the sibling `respan` checkout before running the
examples.

## Basic Example

The fastest way to see a simple Claude Agent SDK trace on Respan platform is:

```bash
yarn basic
```

What it does:

- sends one basic `query()` request
- traces it with `@respan/instrumentation-claude-agent-sdk`
- prints the Claude result locally
- prints the exact platform filters to find the trace

Look up the trace on platform with:

- `customer_identifier = claude-agent-sdk-basic-example`
- `metadata.example_name = claude_agent_sdk_basic_platform_example`

## Advanced Example

The complex edge-case example is also available:

```bash
yarn complex
```

## What The Advanced Example Covers

- Basic `query()` tracing
- Single-tool query with Claude MCP tools
- Multi-tool query with chained tool usage
- Tool error handling
- Stateful multi-turn session using repeated `query()` calls with `resume`

The Python example uses `ClaudeSDKClient`; the current TypeScript SDK surface
exposes the equivalent session flow through resumed `query()` calls, so this
example follows the public TypeScript API.

Look up the advanced trace on platform with:

- `customer_identifier = claude-agent-sdk-complex-edge-cases-v2`
- `metadata.example_name = claude_agent_sdk_complex_edge_cases`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESPAN_GATEWAY_API_KEY` or `RESPAN_API_KEY` | Yes | Used for both Respan tracing and Anthropic-compatible gateway auth |
| `RESPAN_BASE_URL` | No | Defaults to `https://api.respan.ai/api` |
| `CLAUDE_AGENT_MODEL` | No | Defaults to `sonnet` |
