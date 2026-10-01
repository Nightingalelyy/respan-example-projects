# Gateway performance benchmark

Measure streaming latency and output tokens per second with a repeatable workload and a `RESPAN_API_KEY`. The separate [availability checker](README.md) remains available as `run.py`.

## Setup and run

Use the [existing setup](README.md#setup): activate its virtual environment, install `requirements.txt`, and set `RESPAN_API_KEY` in `.env`. No provider key is sent directly. Use a Respan key from the organization whose **Models → Live** list you want to test.

```bash
cd python/gateway/model-testing
source .venv/bin/activate

# Default: Prism DeepSeek V4 Flash and V4.1 Flash
python benchmark.py

# Short smoke check: three measured requests per model
python benchmark.py --runs 3

# Select exact IDs from your platform's Live list
python benchmark.py --model prism/deepseek-v4-flash --runs 10
```

These commands make paid inference requests. The default run makes 22 requests: one warmup and ten measured requests for each of two models. Selection is checked against the platform's current Live catalog; only listed chat models are accepted.

## Workload

| Option | Default | Meaning |
| --- | --- | --- |
| `--model` | `prism/deepseek-v4-flash`, `prism/deepseek-v4.1-flash` | Repeat to select exact model IDs. |
| `--runs` | `10` | Measured requests per model. |
| `--warmup` | `1` | Warmup requests per model, excluded from statistics. |
| `--concurrency` | `1` | Maximum concurrent requests across all models. |
| `--max-tokens` | `256` | Maximum output token budget per request. |
| `--timeout` | `60` | Timeout in seconds per HTTP phase, not a total run deadline. |
| `--prompt-file` | `benchmark-prompt.txt` | UTF-8 prompt shared by every request. |

Temperature is fixed at `0`. Gateway response caching, fallback, and retries are disabled, including client retries. Provider-side prompt/prefix caching may still affect repeated requests. All warmup requests finish before measurement starts. Each phase schedules models in round-robin order without randomization.

The output budget is a maximum, not a guaranteed output length. Use the same prompt, budget, concurrency, and run count when comparing results. Ten samples per model are a small performance check, not evidence of a production SLA.

## Measurements

Timing uses the client's clock, starting immediately before sending each streaming POST:

| Metric | Definition |
| --- | --- |
| TTFT | Time until the first nonempty `content`, `reasoning_content`, or `reasoning` delta. Role-only events, headers, and keepalives do not count. |
| Total latency | Time until the complete stream has been read, including its usage trailer. |
| Output tokens/second | Provider-reported `usage.completion_tokens / (latency_seconds - TTFT_seconds)`. |

The benchmark uses `completion_tokens` exactly as returned. It records `reasoning_tokens` separately and never adds or subtracts that value: provider conventions and breakdowns can differ, so its inclusion in the completion count is not assumed. The benchmark does not estimate tokens from words or streaming chunks. Tokens/second is therefore throughput based on the reported completion count, not an independently verified count of every generated token.

A request with missing completion-token usage, empty output, or no terminal finish reason is an error and is excluded from performance statistics. A clean end of stream after a finish reason is accepted even without a `[DONE]` marker. HTTP errors and timeouts are also retained as error rows.

These are client-observed measurements and include network effects. Platform metrics aggregate actual traffic with varying workloads. Although the backend uses the same tokens/second formula, its server-side first-chunk TTFT differs from this benchmark's first nonempty output delta; the two measurements are not directly interchangeable.

## Reports

Each run writes to `results/benchmark-<timestamp>-<id>/`:

- `requests.csv` and `requests.jsonl`: every warmup and measured request, including errors.
- `summary.json`: settings, prompt text and hash, model IDs, sample and error counts, and per-model p50/p95 TTFT, total latency, and output tokens/second.
- `settings.json`: the workload settings, saved before requests start.

Percentiles use linear interpolation over successful **measured** requests only. Timing is reported in milliseconds and throughput in tokens/second. Always compare sample and error counts alongside percentiles; excluded errors must not be interpreted as fast responses. The saved prompt and settings identify the workload used for the report. Results are Git-ignored.

Exit codes: `0` all requests measured successfully, `1` one or more measurement errors, `2` setup/catalog failure. For interrupted runs, check `complete` and the completed/planned request counts in `summary.json`.
