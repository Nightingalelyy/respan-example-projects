# Anthropic Agent SDK + Respan Examples (TypeScript)

Runnable examples showing how to trace Anthropic Agent SDK queries with Respan.

## Setup

```bash
cd typescript/tracing/anthropic-agents-sdk

# Install dependencies
npm install
# or: yarn install

# Copy and fill in your keys
cp .env.example .env
```

## Examples

### hello_world_test.ts
The simplest example — ask Claude a question, see the trace in Respan.
```bash
npx tsx hello_world_test.ts
```

### wrapped_query_test.ts
One-liner integration using `exporter.query()` — handles everything automatically.
```bash
npx tsx wrapped_query_test.ts
```

### gateway_test.ts
Route through the Respan gateway — only needs `RESPAN_API_KEY`, no Anthropic key.
```bash
npx tsx gateway_test.ts
```

### tool_use_test.ts
Run a query with tools (Read, Glob, Grep) and see tool spans in the trace.
```bash
npx tsx tool_use_test.ts
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESPAN_API_KEY` | Yes | Your Respan API key |
| `ANTHROPIC_API_KEY` | For non-gateway examples | Your Anthropic API key |
| `RESPAN_BASE_URL` | No | Override ingest URL (default: `https://api.respan.ai/api`) |
| `RESPAN_GATEWAY_BASE_URL` | For gateway example | Gateway URL (default: `https://api.respan.ai/api`) |
