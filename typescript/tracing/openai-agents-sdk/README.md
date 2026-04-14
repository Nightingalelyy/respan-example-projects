# OpenAI Agents SDK + Respan Example (TypeScript)

Runnable stress-test example showing how to trace the OpenAI Agents SDK with Respan from the example repository.

This package mirrors the Python reference at `python/tracing/openai-agents-sdk/complex_edge_cases_test.py` and uses the local `@respan/instrumentation-openai-agents` package from the sibling `respan` checkout.

## Setup

```bash
cd typescript/tracing/openai-agents-sdk

# Install dependencies
yarn install

# Optional: create a local env file for this package
cp .env.example .env
```

The script also falls back to the repository root `.env` if you already keep shared credentials there.

## Run

```bash
yarn complex
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESPAN_API_KEY` | Yes | Your Respan API key |
| `RESPAN_BASE_URL` | No | Override the gateway / ingest base URL |
| `RESPAN_MODEL` | No | Override the model name used by the example |
