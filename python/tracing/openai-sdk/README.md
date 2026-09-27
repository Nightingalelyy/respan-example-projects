# OpenAI SDK tracing examples

These 20 scripts exercise the real OpenAI sync and async clients, validated with
**OpenAI 3.19.2**. The deterministic suite uses `httpx2.MockTransport` to supply
valid response payloads. No provider credential or managed prompt is required;
requests still pass through official SDK resources, SSE, parse, and error classes.

The examples cover Chat and Responses, sync/async structured parsing, streaming,
two-turn tools, embeddings, precise 401 handling, propagated attributes,
decorators, prompt-shaped requests, and deterministic batch result logging.
`stream_helpers.py` and `async_stream_helpers.py` each exercise five calls:
complete and early-close Chat helpers, complete and early-close Responses
helpers, and an early-close raw Responses stream. Partial spans must retain
observed text, finish when the context exits, and omit usage that was not received.

## Run

From this directory, install the requirements and link the target local package:

```bash
python -m pip install -r requirements.txt "respan-ai==4.1.0" \
  "respan-tracing==2.20.0" "respan-sdk==2.7.6" "opentelemetry-sdk==1.45.0"
python -m pip install --no-deps -e ../../../../respan/python-sdks/instrumentations/respan-instrumentation-openai
RESPAN_EXAMPLE_RUN_ID=openai-py-20260927T120000Z python run_all.py
```

For this package's pre-release source version `1.2.0`, use released
`respan-ai==4.1.0` when validating the editable checkout: newer facade releases
require a newer instrumentation distribution version. The validated isolated
environment uses `respan-tracing==2.20.0`, `respan-sdk==2.7.6`, and
`opentelemetry-sdk==1.45.0`; only the target instrumentation is editable.
Run `python -m pip check` and verify the editable distribution's `direct_url.json`
before auditing local changes.

Set `RESPAN_API_KEY` in the repository root `.env` or shell; `RESPAN_BASE_URL`
optionally selects the trace endpoint. `run_all.py` preserves the shell's exact
run marker, forces deterministic child execution, and reports all failures after
the set finishes. Every script closes its clients, flushes, and shuts down Respan.
Root trace IDs are printed for scoped platform inspection. For local evidence,
`RESPAN_EXAMPLE_SPANS_PATH=/absolute/path/spans.jsonl` also records span attributes.
This file includes example input/output; it is optional and is not committed.

## Optional live provider

Use the separate live script for one real Chat request:

```bash
export OPENAI_API_KEY=...
# Optional for an OpenAI-compatible Chat endpoint:
# export OPENAI_BASE_URL=...
RESPAN_OPENAI_LIVE=1 RESPAN_EXAMPLE_RUN_ID=openai-py-live-20260927T120000Z python live_provider.py
```

`RESPAN_OPENAI_MODEL` defaults to `gpt-4.1-nano`. The endpoint must support Chat
Completions; this does not establish its Responses support. Batch examples use
deterministic results because provider-side file upload and polling are outside
this instrumentation. Managed-prompt-shaped fixtures use `RESPAN_PROMPT_ID` when
supplied.
