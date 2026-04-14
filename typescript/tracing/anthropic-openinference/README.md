# Anthropic + OpenInference + Respan (TypeScript)

Runnable TypeScript example showing the OpenInference Anthropic path with local Respan packages.

This mirrors `python/tracing/respan-tracing-sdk/anthropic_openinference_example.py`:

1. Initialize `RespanTelemetry`
2. Activate local `@respan/instrumentation-openinference` with `@arizeai/openinference-instrumentation-anthropic`
3. Call the Anthropic SDK normally through the Respan gateway

## Setup

```bash
cd typescript/tracing/anthropic-openinference
yarn install
cp .env.example .env
```

The script also falls back to the example repo root `.env` if you already keep shared credentials there.

## Run

```bash
yarn example
```

## Notes

- This package links the local `@respan/instrumentation-openinference`, `@respan/tracing`, and `@respan/respan-sdk` packages from the sibling `respan` checkout so fixes can be tested immediately.
- Anthropic auto-instrumentation is disabled on purpose so this example uses the explicit OpenInference wrapper path.
