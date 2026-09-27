# OpenAI SDK tracing examples

This suite validates `@respan/instrumentation-openai` with OpenAI **7.23.0**.
It uses released Respan core packages and the local instrumentation checkout.
The real OpenAI SDK handles all requests, parsing, API promises, and SSE streams;
only its HTTP `fetch` transport is replaced with deterministic fixture responses.

The 16 scenarios cover Chat and Responses, streaming, parsed output, two-turn
function calls with tool execution spans, streaming tool arguments, embeddings,
text completions, `.withResponse()`, early stream cancellation, and a precise
401 failure. Expected trace shape is 16 workflows and 20 children: 18 provider
spans and two tool spans. A passing process is only the first validation step;
inspect the exported traces in Respan to verify their content and parents.

## Run the deterministic suite

Keep `respan` and `respan-example-projects` as sibling checkouts. Build the local
`@respan/instrumentation-openai` package in the `respan` JavaScript workspace,
then run from this directory:

```bash
npm install
npm run typecheck
RESPAN_EXAMPLE_RUN_ID=openai-ts-20260927T120000Z npm run all
```

Set `RESPAN_API_KEY` in the repository root `.env` or shell; `RESPAN_BASE_URL`
optionally selects the trace endpoint. Each workflow prints its trace ID and
propagates the exact run marker as metadata and in `custom_identifier`.
`npm run all` always uses fixtures and attempts every scenario before reporting
failures. It flushes and shuts down tracing even after a failure.

## Opt-in live provider

The separate live script sends one real Chat request. It does not run fixture
error cases or embeddings against an endpoint that may not support them.

```bash
export OPENAI_API_KEY=...
# Optional for an OpenAI-compatible Chat endpoint:
# export OPENAI_BASE_URL=...
RESPAN_OPENAI_LIVE=1 RESPAN_EXAMPLE_RUN_ID=openai-ts-live-20260927T120000Z npm run live
```

`RESPAN_OPENAI_MODEL` defaults to `gpt-4.1-nano`. A compatible endpoint must
support Chat Completions; this script does not establish its Responses support.
