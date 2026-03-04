# Pydantic AI Respan Integration Example

This example demonstrates how to integrate `pydantic-ai` with Respan tracing using `respan-exporter-pydantic-ai`.

## Setup

1. Install the required dependencies:

```bash
cd python/tracing/pydantic-ai
pip install -r requirements.txt
```

2. Set your environment variables:

```bash
cp .env.example .env
```
Then edit `.env` and fill in your actual API keys.

3. Run the example script:

```bash
python example.py
```

## How it works

1. `RespanTelemetry` initializes the OpenTelemetry pipeline for Respan.
2. `instrument_pydantic_ai()` intercepts calls made by the `pydantic-ai` Agents.
3. The traces, spans, and metrics from LLM calls are sent to Respan, available in the dashboard.

## Further reading

- [Respan Example Projects](https://github.com/respanai/respan-example-projects/tree/main)
