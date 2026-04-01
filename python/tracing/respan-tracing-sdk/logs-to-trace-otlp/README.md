# Logs to Trace (OTLP v2) Example

This example demonstrates how to send traces to Respan using the [OTLP v2 endpoint](https://www.respan.ai/docs/api-reference/observe/traces/ingest-traces-via-otlp), the same protocol used by the `respan-tracing` SDK and OpenTelemetry exporters.

## Why OTLP v2?

The v2 endpoint (`/api/v2/traces`) uses the standard [OpenTelemetry Protocol (OTLP)](https://opentelemetry.io/docs/specs/otlp/) format. This is ideal when:

- You're in a custom runtime (e.g., Cloudflare Workers) where the SDK can't be used
- You want to use standard OTLP tooling and conventions
- You need to set `respan.entity.log_type` to differentiate span types (workflow, agent, tool, chat, etc.)

## Span Types (log_type)

The sample trace demonstrates different span types via the `respan.entity.log_type` attribute:

| log_type | Description | Example |
|----------|-------------|---------|
| `workflow` | Top-level pipeline orchestration | `customer_support_pipeline` |
| `agent` | AI agent handling a conversation | `support_agent` |
| `tool` | Function/tool calls | `lookup_order`, `process_refund` |
| `chat` | LLM inference calls | `openai.chat` (with token usage) |
| `task` | Utility operations | `log_resolution` |

Other supported types: `completion`, `response`, `embedding`, `transcription`, `speech`, `handoff`, `guardrail`, `generation`, `function`, `custom`

## How it works

1. Loads sample OTLP trace data from `trace_spans.json`
2. Shifts timestamps to current time while preserving relative timing
3. Remaps `traceId`, `spanId`, and `parentSpanId` to prevent conflicts
4. Sends the OTLP payload to `POST /api/v2/traces`

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables (or create a `.env` file):

- `RESPAN_API_KEY`: Your Respan API key
- `RESPAN_BASE_URL`: Respan base URL (default: `https://api.respan.ai/api`)

## Usage

```bash
python main.py
```

## Key Differences from v1 (`/api/v1/traces/ingest`)

| | v1 (Logs Ingest) | v2 (OTLP) |
|---|---|---|
| Format | Flat JSON array of spans | OTLP `ExportTraceServiceRequest` |
| Span type | Via `span_name` suffix | Via `respan.entity.log_type` attribute |
| Timestamps | ISO 8601 strings | Unix nanoseconds |
| Attributes | Top-level fields | OTLP typed key-value pairs |
| Gen AI fields | `prompt_messages`, `completion_message` | `gen_ai.prompt.N.*`, `gen_ai.completion.N.*` |

## OTLP Payload Structure

```
resourceSpans[]
  └─ resource.attributes[]        # service.name, etc.
  └─ scopeSpans[]
      └─ scope                    # instrumentation library
      └─ spans[]
          ├─ traceId              # 32-char hex
          ├─ spanId               # 16-char hex
          ├─ parentSpanId         # links to parent
          ├─ name                 # operation name
          ├─ startTimeUnixNano    # nanosecond timestamp
          ├─ endTimeUnixNano
          ├─ attributes[]         # respan.entity.log_type, gen_ai.*, etc.
          └─ status               # {code: 1} for OK
```

Learn more: [OTLP Traces API Reference](https://www.respan.ai/docs/api-reference/observe/traces/ingest-traces-via-otlp)
