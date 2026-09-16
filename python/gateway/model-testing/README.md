# Gateway model availability

Check whether models listed in [platform.respan.ai → Models → Live](https://platform.respan.ai/platform/gateway/models) can be called with your `RESPAN_API_KEY`. Each model receives one small request. Results contain its model ID, provider, HTTP status, latency, and error, saved as JSON and CSV.

For repeated streaming TTFT, tokens-per-second, and latency measurements, use the
separate [performance benchmark](BENCHMARK.md) (`python benchmark.py`).
The availability commands below continue to use `run.py`.

## Setup

Requires Python 3.9+.

```bash
cd python/gateway/model-testing
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `RESPAN_API_KEY` in `.env`. The script also reads the repository-root `.env`; existing shell variables take precedence. `RESPAN_BASE_URL` defaults to `https://api.respan.ai/api`.

## Run

```bash
# List models without making inference calls
python run.py --list

# Check all live models
python run.py

# Check specific models
python run.py --model openai/gpt-4o-mini --model openai/text-embedding-ada-002
```

Optional: `--workers 4`, `--timeout 60` (seconds per HTTP phase), and `--max-tokens 64` (chat output budget). All-model runs make paid inference requests.

The script reads every page of `/api/models/list/?status=active`, matching the platform's **Live** filter, and uses the exact model IDs returned there. Archived models and aliases absent from that list are excluded; `/models/public` is never queried. The API key selects the organization, so use a key from the same organization you view on the platform. It uses chat, embedding, or audio requests according to model type. Discovery failures stop the run rather than returning partial coverage.

## Results

Each run writes to `results/availability-<timestamp>-<id>/`:

- `models.json`: models selected for this run.
- `results.csv`: one availability row per model.
- `results.json`: the same results with counts and a `complete` flag.
- `results.jsonl`: results saved as each request finishes, preserving partial progress.

`available` means the Gateway returned a successful inference response. The response does not need to contain a particular answer. `unavailable` preserves the HTTP error, timeout, or invalid-response detail. `not_tested` means the model type needs an adapter.

Availability is specific to **this key, request, and time**. A live catalog entry can still require a connected provider key, credits, or different request parameters. A short reasoning budget may produce an empty answer; a successful inference response still counts as available. Cache, fallback, and retries are disabled for these checks. No provider keys are sent directly.

Exit codes: `0` all available (or listing completed), `1` some models unavailable/not tested, `2` setup or discovery failure. An interrupted run retains partial results; check `complete` before treating it as a full sweep. Reports and `.env` are Git-ignored.

See [Gateway setup](https://www.respan.ai/docs/documentation/features/gateway/gateway-quickstart) and [model availability and billing](https://www.respan.ai/docs/documentation/features/gateway/models-catalog).

## Local tests

```bash
python -m unittest discover -s tests -q
```

Tests use mocked HTTP responses and make no model calls. The short [speech fixture](fixtures/README.md) is used only for transcription models.
