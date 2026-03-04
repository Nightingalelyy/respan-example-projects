# Pydantic AI Respan Integration Example

This example demonstrates how to integrate `pydantic-ai` with Respan tracing using `respan-exporter-pydantic-ai`.

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Set your environment variables:

```bash
export RESPAN_API_KEY="your-respan-api-key"
export OPENAI_API_KEY="your-openai-api-key"
```

3. Run the example script:

```bash
python example.py
```

## How it works

1. `RespanTelemetry` initializes the OpenTelemetry pipeline for Respan.
2. `instrument_pydantic_ai()` intercepts calls made by the `pydantic-ai` Agents.
3. The traces, spans, and metrics from LLM calls are sent to Respan, available in the dashboard.
