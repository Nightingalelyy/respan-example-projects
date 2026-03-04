# Anthropic Agent SDK + Respan Examples (Python)

Runnable examples showing how to trace Anthropic Agent SDK queries with Respan.

## Setup

```bash
cd python/tracing/anthropic-agents-sdk

# Install dependencies
pip install claude-agent-sdk respan-exporter-anthropic-agents python-dotenv

# Copy and fill in your keys
cp .env.example .env
```

## Examples

### basic/hello_world_test.py
The simplest example — ask Claude a question, see the trace in Respan.
```bash
python basic/hello_world_test.py
```

### basic/wrapped_query_test.py
One-liner integration using `exporter.query()` — handles everything automatically.
```bash
python basic/wrapped_query_test.py
```

### basic/gateway_test.py
Route through the Respan gateway — only needs `RESPAN_API_KEY`, no Anthropic key.
```bash
python basic/gateway_test.py
```

### basic/tool_use_test.py
Run a query with tools (Read, Glob, Grep) and see tool spans in the trace.
```bash
python basic/tool_use_test.py
```

## Running with pytest

```bash
pip install pytest pytest-asyncio
pytest basic/ -v
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESPAN_API_KEY` | Yes | Your Respan API key |
| `ANTHROPIC_API_KEY` | For non-gateway examples | Your Anthropic API key |
| `RESPAN_BASE_URL` | No | Override ingest URL (default: `https://api.respan.ai/api`) |
| `RESPAN_GATEWAY_BASE_URL` | For gateway example | Gateway URL (default: `https://api.respan.ai/api`) |
