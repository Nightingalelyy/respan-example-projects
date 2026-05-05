# Haystack + Respan Complex Tracing Example

This example exercises Haystack indexing, retrieval, routing, prompt building,
joining, answer building, custom components, and generator-shaped spans with
`respan-instrumentation-haystack`.

It uses a deterministic local generator, so no live LLM key is required. Traces
are still exported to Respan through the normal tracing SDK.

## Run

```bash
cd /home/yuyang/KeywordsAI/respan-example-projects
python python/tracing/haystack/complex_edge_cases.py
```

Set `RESPAN_HAYSTACK_RUN_ID` to make the run easy to find in Respan:

```bash
RESPAN_HAYSTACK_RUN_ID=haystack-local-test \
python python/tracing/haystack/complex_edge_cases.py
```
