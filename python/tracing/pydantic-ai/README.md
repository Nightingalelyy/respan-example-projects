# Pydantic AI Respan Integration Examples

These examples demonstrate how to integrate `pydantic-ai` with Respan tracing using `respan-exporter-pydantic-ai`.

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
Then edit `.env` and set your Respan API key. All examples route LLM calls through Respan, so no OpenAI key is needed.

## Examples

We provide 5 examples demonstrating different aspects of the integration:

| Example | Description |
|---------|-------------|
| `01_hello_world.py` | Bare minimum sanity check — does this integration work? |
| `02_gateway.py` | Route LLM calls through Respan proxy |
| `03_tracing.py` | Workflow/task spans with `RespanTelemetry`, `@workflow`, and `@task` decorators |
| `04_respan_params.py` | Setting `customer_identifier`, `metadata`, and `custom_tags` on spans |
| `05_tool_use.py` | Tracing a Pydantic AI agent that uses tools |

Run any example like this:

```bash
python 02_gateway.py
```

## How it works

1. `RespanTelemetry` initializes the OpenTelemetry pipeline for Respan.
2. `instrument_pydantic_ai()` intercepts calls made by the `pydantic-ai` Agents.
3. The traces, spans, and metrics from LLM calls (and tools/workflows) are sent to Respan, available in the dashboard.
4. **Gateway pattern**: By pointing `OPENAI_BASE_URL` and `OPENAI_API_KEY` to Respan, LLM calls are routed through Respan, so only `RESPAN_API_KEY` is required.

## Further reading

- [Respan Example Projects](https://github.com/respanai/respan-example-projects/tree/main)
